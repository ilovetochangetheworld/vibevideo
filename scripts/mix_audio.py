#!/usr/bin/env python3
"""Explicit-stem mixer. With/without BGM exports, shared voice/effect gains, fixed mastering gain.
Usage: python mix_audio.py /absolute/project/mix.json
Requires numpy, ffmpeg and ffprobe. Paths resolve against the JSON directory.
"""
import argparse,hashlib,json,math,re,subprocess,wave
from pathlib import Path
import numpy as np
SR=48000

def call(args):
 return subprocess.run(args,check=True,capture_output=True)
def probe(p):return json.loads(call(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]).stdout)
def decode(p,seconds,start=0,filters=None):
 args=['ffmpeg','-v','error','-ss',str(start),'-i',str(p),'-t',str(seconds)]
 if filters:args+=['-af',filters]
 args+=['-f','f32le','-ar',str(SR),'-ac','2','-']
 return np.frombuffer(call(args).stdout,dtype='<f4').reshape(-1,2).copy()
def wav(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 if np.abs(x).max(initial=0)>=1:raise ValueError('PCM would clip; reduce stem gains')
 with wave.open(str(p),'wb') as f:
  f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(np.round(x*32767).astype('<i2').tobytes())
def measure(p):
 q=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af','loudnorm=I=-16:TP=-2:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
 return json.loads(re.findall(r'\{[^{}]+\}',q.stderr,re.S)[-1])
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('spec',type=Path);a=ap.parse_args()
 specpath=a.spec.resolve();root=specpath.parent;s=json.loads(specpath.read_text())
 def path(v):return (root/v).resolve()
 video=path(s['video']);out=path(s['output']);vp=probe(video)
 duration=float(s.get('duration') or vp['format']['duration']);n=round(duration*SR)
 if duration<=0:raise ValueError('duration must be positive')
 work=out.parent/(out.stem+'-audio');work.mkdir(parents=True,exist_ok=True)
 stems=[];mix=np.zeros((n,2),np.float32);no_bgm=np.zeros((n,2),np.float32)
 no_out=path(s.get("output_no_bgm",str(Path(s["output"]).with_name(Path(s["output"]).stem+"-no-bgm.mp4"))))
 sources=[video]+[path(c["file"]) for c in [s.get("voice"),s.get("bgm"),*s.get("effects",[])] if c]
 outputs=[out,no_out] if s.get("bgm") else [out]
 if len(set(outputs))!=len(outputs) or any(o in sources for o in outputs):raise ValueError("Outputs must be distinct and must not replace inputs")
 def add_track(cfg,kind):
  p=path(cfg['file']);start=float(cfg.get('start',0));gain=float(cfg.get('gain_db',0));filters=None
  if kind=='voice':filters=cfg.get('filter','highpass=f=80,loudnorm=I=-18:TP=-4:LRA=7')
  if kind=='bgm':filters=cfg.get('filter','highpass=f=55,lowpass=f=14000')
  x=decode(p,duration,start,filters)
  if len(x)>n:x=x[:n]
  if kind=='bgm' and len(x)<n-100:raise ValueError('BGM excerpt is too short; choose another start or prepare a deliberate loop')
  if len(x)<n:x=np.pad(x,((0,n-len(x)),(0,0)))
  original_rms=float(np.sqrt(np.mean(x*x)))
  if kind=='bgm':
   if original_rms<1e-7:raise ValueError('BGM excerpt is silent')
   gain+=float(cfg.get('rms_db',-28))-20*math.log10(original_rms)
  x*=10**(gain/20)
  # Only whole-film edge fades; there is no voice-activity envelope.
  fi=float(cfg.get('fade_in',.7 if kind=='bgm' else 0));fo=float(cfg.get('fade_out',1.4 if kind=='bgm' else 0))
  envelope=np.ones(n,np.float32)
  if fi>0:envelope=np.minimum(envelope,np.arange(n)/(fi*SR))
  if fo>0:envelope=np.minimum(envelope,(n-1-np.arange(n))/(fo*SR))
  x*=np.clip(envelope,0,1)[:,None]
  nonlocal mix,no_bgm;mix+=x
  if kind!="bgm":no_bgm+=x
  wav(work/(kind+f'-{len(stems)}.wav'),x)
  stems.append({'kind':kind,'file':str(p),'sha256':digest(p),'start':start,'gain_db':gain,'fade_in':fi,'fade_out':fo,'speech_ducking':False,'filter':filters})
 if s.get('voice'):add_track(s['voice'],'voice')
 if s.get('bgm'):add_track(s['bgm'],'bgm')
 for effect in s.get('effects',[]):add_track(effect,'effect')
 # Both deliveries use exactly the same voice/effect processing and master scalar.
 # Account for peaks in both mixes: removing music can remove cancellation.
 peak=max(float(np.abs(mix).max(initial=0)),float(np.abs(no_bgm).max(initial=0)))
 pregain=min(1,.9/max(peak,1e-8));mix*=pregain;no_bgm*=pregain
 prem=work/'premaster.wav';wav(prem,mix)
 prem_no=work/'premaster-no-bgm.wav';wav(prem_no,no_bgm)
 main_audible=bool(np.any(mix));no_audible=bool(np.any(no_bgm))
 m=measure(prem) if main_audible else None
 mn=measure(prem_no) if no_audible else None
 if main_audible:
  input_i=float(m['input_i'])
  if not math.isfinite(input_i):raise ValueError('Mix has no measurable loudness')
  max_tp=max(float(x['input_tp']) for x in [m,mn] if x)
  gain_db=min(float(s.get('target_lufs',-16))-input_i,float(s.get('true_peak_ceiling_db',-2))-max_tp)
 else:gain_db=0
 scalar=10**(gain_db/20);mix*=scalar;no_bgm*=scalar
 master=work/'master.wav';wav(master,mix)
 master_no=work/'master-no-bgm.wav';wav(master_no,no_bgm)
 def export(dest,audio,audible,include_bgm):
  dest.parent.mkdir(parents=True,exist_ok=True)
  args=['ffmpeg','-v','error','-y','-i',str(video)]
  if audible:args+=['-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k']
  else:args+=['-map','0:v:0','-c:v','copy','-an']
  args+=['-t',str(duration),'-movflags','+faststart','-metadata','title='+s.get('title',out.stem)+(' | with BGM' if include_bgm else ' | no BGM')]
  credit=s.get('credit') if include_bgm else s.get('credit_no_bgm')
  if credit:args+=['-metadata','comment='+credit]
  call(args+[str(dest)])
  call(['ffmpeg','-v','error','-i',str(dest),'-f','null','-'])
  final=probe(dest);loud=measure(dest) if audible else None
  used=[x for x in stems if include_bgm or x['kind']!='bgm']
  report={'output':str(dest),'variant':'with-bgm' if include_bgm else 'no-bgm','duration':duration,'stems':used,'bgm_count':sum(x['kind']=='bgm' for x in used),'embedded_video_audio_used':False,'speech_ducking':False,'premaster_scale':pregain,'master_gain_db':gain_db,'mastering':'shared constant gain across versions; no mix compression or BGM automation','audio_present':audible,'delivered_loudness':{k:loud[k] for k in ['input_i','input_tp','input_lra']} if loud else None,'decode':'passed','streams':[{k:v[k] for k in ['codec_type','codec_name','width','height','r_frame_rate','nb_frames'] if k in v} for v in final['streams']]}
  dest_work=dest.parent/(dest.stem+'-audio');dest_work.mkdir(parents=True,exist_ok=True)
  (dest_work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  return report
 reports=[export(out,master,main_audible,bool(s.get('bgm')))]
 if s.get('bgm'):reports.append(export(no_out,master_no,no_audible,False))
 summary={'variants':reports,'shared_voice_and_effect_gain':True,'without_bgm_master':str(master_no)}
 (work/'variants.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
