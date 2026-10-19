#!/usr/bin/env python3
"""Synthesize aligned Chinese narration. Cue JSON: [{start,end,text}, ...].
Usage: python tts.py cues.json --out audio/voice --voice zh-CN-YunyangNeural
Requires edge-tts, numpy and ffmpeg/ffprobe. Reuses matching, valid cached clips.
"""
import argparse,asyncio,hashlib,json,subprocess,wave
from pathlib import Path
import edge_tts
import numpy as np

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('cues',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--voice',default='zh-CN-YunyangNeural');p.add_argument('--rate',default='+6%');p.add_argument('--pitch',default='-2Hz');p.add_argument('--duration',type=float);a=p.parse_args()
 cues=json.loads(a.cues.read_text());a.out.mkdir(parents=True,exist_ok=True)
 if not cues:raise SystemExit('No narration cues')
 prev=0
 for c in cues:
  if not (0<=c['start']<c['end']) or c['start']<prev:raise SystemExit('Cues must be ordered and non-overlapping')
  if not c['text'].strip():raise SystemExit('Empty narration text')
  prev=c['end']
 duration=a.duration or max(c['end'] for c in cues)
 if duration<prev:raise SystemExit('Duration is shorter than the narration windows')
 sem=asyncio.Semaphore(2)
 async def generate(i,c):
  async with sem:
   params={'text':c['text'],'voice':a.voice,'rate':a.rate,'pitch':a.pitch}
   key=hashlib.sha256(json.dumps(params,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:14]
   f=a.out/f'{i+1:02}-{key}.mp3'
   if not f.exists() or f.stat().st_size<1000:
    for attempt in range(2):
     try:
      await asyncio.wait_for(edge_tts.Communicate(**params).save(str(f)),45);break
     except Exception:
      if attempt:raise
      await asyncio.sleep(1)
   pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(f),'-ar','48000','-ac','2','-f','f32le','-'])
   x=np.frombuffer(pcm,dtype='<f4').reshape(-1,2).copy();seconds=len(x)/48000
   if seconds>c['end']-c['start']:
    raise ValueError(f'Cue {i+1} needs {seconds:.2f}s; window is {c["end"]-c["start"]:.2f}s. Widen the timeline or regenerate modestly faster; do not cut the words.')
   rms=np.sqrt(np.mean(x*x));peak=np.abs(x).max(initial=0)
   x*=min(.115/max(rms,1e-8),.70/max(peak,1e-8))
   n=min(384,len(x));x[:n]*=np.linspace(0,1,n)[:,None];x[-n:]*=np.linspace(1,0,n)[:,None]
   return c|params|{'file':f.name,'duration':seconds},x
 async def run():return await asyncio.gather(*(generate(i,c) for i,c in enumerate(cues)))
 result=asyncio.run(run());bus=np.zeros((round(duration*48000),2),np.float32)
 for c,x in result:
  at=round(c['start']*48000);bus[at:at+len(x)]+=x
 if np.abs(bus).max(initial=0)>=1:raise SystemExit('Narration PCM clipping')
 with wave.open(str(a.out/'narration.wav'),'wb') as w:
  w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(np.round(bus*32767).astype('<i2').tobytes())
 (a.out/'narration.json').write_text(json.dumps([c for c,_ in result],ensure_ascii=False,indent=2))
 print(a.out/'narration.wav')
if __name__=='__main__':main()
