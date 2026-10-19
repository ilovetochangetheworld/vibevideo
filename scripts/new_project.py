#!/usr/bin/env python3
"""Create an empty Canvas knowledge-film project, outside the skill directory."""
import argparse,json,shutil
from pathlib import Path
S=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('--title',default='知识短片');p.add_argument('--duration',type=float,default=36);a=p.parse_args()
out=a.project.resolve()
if out==S or S in out.parents:raise SystemExit('Create the project outside the skill directory')
if out.exists() and any(out.iterdir()):raise SystemExit('Project directory is not empty; inspect and edit it in place')
if a.duration<=0:raise SystemExit('Duration must be positive')
out.mkdir(parents=True,exist_ok=True)
for folder in ['audio','renders','review']: (out/folder).mkdir(exist_ok=True)
shutil.copy(S/'assets/engine/index.html',out/'index.html')
(out/'film.js').write_text('''(function(){
'use strict';
const K=VKit;
const SUBS=[];
VK.film({dur:DURATION,theme:'night',bloom:.23,grain:.025,meta:{title:TITLE},
 draw(fr,t){
  // Write original scene functions from storyboard.md. No audio is mixed here.
  K.subs(fr,t,SUBS,'night');
 }
});
})();
'''.replace('DURATION',str(a.duration)).replace('TITLE',json.dumps(a.title,ensure_ascii=False)))
print(out)
