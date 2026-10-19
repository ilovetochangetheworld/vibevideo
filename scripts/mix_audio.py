#!/usr/bin/env python3
"""Explicit-stem mixer. One BGM, no speech-triggered ducking, fixed mastering gain.
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
 stems=[];mix=np.zeros((n,2),np.float32)
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
  nonlocal mix;mix+=x
  wav(work/(kind+f'-{len(stems)}.wav'),x)
  stems.append({'kind':kind,'file':str(p),'sha256':digest(p),'start':start,'gain_db':gain,'fade_in':fi,'fade_out':fo,'speech_ducking':False,'filter':filters})
 if s.get('voice'):add_track(s['voice'],'voice')
 if s.get('bgm'):add_track(s['bgm'],'bgm')
 for effect in s.get('effects',[]):add_track(effect,'effect')
 if not stems:raise ValueError('No explicit audio stems supplied')
 prem=work/'premaster.wav';peak=float(np.abs(mix).max(initial=0))
 # Avoid PCM clipping prior to measuring. This is one fixed scalar, never a time envelope.
 pregain=min(1,.9/max(peak,1e-8));mix*=pregain;wav(prem,mix)
 m=measure(prem);input_i=float(m['input_i']);input_tp=float(m['input_tp'])
 if not math.isfinite(input_i):raise ValueError('Mix is silent')
 gain_db=min(float(s.get('target_lufs',-16))-input_i,float(s.get('true_peak_ceiling_db',-2))-input_tp)
 mix*=10**(gain_db/20);master=work/'master.wav';wav(master,mix)
 out.parent.mkdir(parents=True,exist_ok=True)
 sources=[video]+[Path(x['file']) for x in stems]
 if out in sources:raise ValueError('output must not replace an input')
 args=['ffmpeg','-v','error','-y','-i',str(video),'-i',str(master),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-t',str(duration),'-movflags','+faststart','-metadata','title='+s.get('title',out.stem)]
 if s.get('credit'):args+=['-metadata','comment='+s['credit']]
 call(args+[str(out)])
 # Decode the actual delivered file, not just its source stems.
 call(['ffmpeg','-v','error','-i',str(out),'-f','null','-'])
 final=probe(out);loud=measure(out)
 report={'output':str(out),'duration':duration,'stems':stems,'bgm_count':sum(x['kind']=='bgm' for x in stems),'embedded_video_audio_used':False,'speech_ducking':False,'premaster_scale':pregain,'master_gain_db':gain_db,'mastering':'single constant master gain; no mix compression or BGM automation','delivered_loudness':{k:loud[k] for k in ['input_i','input_tp','input_lra']},'streams':[{k:v[k] for k in ['codec_type','codec_name','width','height','r_frame_rate','nb_frames'] if k in v} for v in final['streams']]}
 (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
