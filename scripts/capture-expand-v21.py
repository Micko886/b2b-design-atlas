#!/usr/bin/env python3
"""V2.1 staged real B2B company and inner-page captures, with source URLs.
Only actual Chromium screenshots; no copied images, synthetic UIs, or manufactured sections.
"""
import asyncio,datetime,io,json,re
from pathlib import Path
from PIL import Image,ImageStat,ImageChops,ImageDraw
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
SHOT=ROOT/'screenshots'
OUT=SHOT/'research-v21'
CONF=json.loads((ROOT/'research-v21-candidates.json').read_text())
AUDIT=[]
BG="#f5f5f5"
C_RE=re.compile(r'\b(cookies?|privacy|consent)\b',re.I)
CHALLENGE=re.compile(r'just a moment|verify you are human|checking your browser|access denied|robot check|captcha|enable javascript',re.I)
PATS=[
 re.compile(r'^(reject all|decline all|reject optional|only necessary|necessary only|essential only|reject all cookies|do not accept|accept necessary|allow necessary only|use necessary cookies only)$',re.I),
 re.compile(r'^(accept all|accept cookies|okay|ok|got it|continue)$',re.I),
]
def variation(im):
 st=ImageStat.Stat(im.resize((96,64)).convert('RGB'))
 return max(st.stddev)
def store(im,path):
 path.parent.mkdir(parents=True,exist_ok=True)
 im.convert('RGB').save(path,'WEBP',quality=83,method=5)
async def dismiss(page):
 for trial in range(2):
  for frame in page.frames:
   for pattern in PATS:
    try:
     b=frame.get_by_role('button',name=pattern).first
     if await b.count() and await b.is_visible(timeout=450):
      await b.click(timeout=1900)
      await page.wait_for_timeout(450)
      return True
    except Exception:pass
  await page.wait_for_timeout(500)
 return False
async def screenshot(page,y):
 await page.evaluate('(y)=>window.scrollTo({top:y,behavior:"instant"})',y)
 await page.evaluate("""async()=>{document.querySelectorAll('img[loading="lazy"]').forEach(x=>x.loading='eager');try{await document.fonts.ready}catch(e){}}""")
 await page.wait_for_timeout(1100)
 buf=await page.screenshot(type='png',full_page=False,animations='disabled',timeout=16000)
 return Image.open(io.BytesIO(buf)).convert('RGB')
def snippet_check(title,body):
 if CHALLENGE.search(title+" "+body[:700]):raise ValueError("Blocked or bot challenge")
 if len(body.strip())<100:raise ValueError("Not enough real visible page text")
def note_module(site_id,nid,category,title,lesson,summary,url,image,crop_top=95):
 note=dict(id=nid,site_id=site_id,type=category,title=title,pattern=category+' layout reference',
           url=url,summary=summary,lesson=lesson)
 crop_bottom=min(850,image.height-20)
 if crop_bottom<=crop_top+250:raise ValueError("Screenshot is too short for a real crop")
 crop=image.crop((0,crop_top,image.width,crop_bottom))
 store(image,SHOT/'notes'/(nid+'.webp'))
 store(crop,SHOT/'modules'/(nid+'.webp'))
 module=dict(id=nid,site_id=site_id,page_id=nid,category=category,type=category,title=title,
             lesson=lesson,summary=summary,url=url,
             source_capture='/screenshots/notes/'+nid+'.webp',
             image_file=nid+'.webp',crop_px=[0,crop_top,image.width,crop_bottom],
             reference_type="Real page screenshot — browser region")
 return note,module
async def open_browser(browser,url):
 page=await browser.new_page(viewport={'width':1440,'height':920},device_scale_factor=1,
    locale='en-US',color_scheme='light')
 resp=await page.goto(url,wait_until='domcontentloaded',timeout=27000)
 if not resp or resp.status>=400:
  await page.close()
  raise ValueError("HTTP "+str(resp.status if resp else "unavailable"))
 await page.wait_for_timeout(1400)
 title=(await page.title())[:150]
 body=(await page.locator('body').inner_text(timeout=4500))[:3500]
 snippet_check(title,body)
 clicked=await dismiss(page)
 await page.keyboard.press("Escape")
 await page.mouse.move(1407,900)
 return page,title,clicked
async def home_capture(browser,sem,row,existing):
 sid=row['id']
 if sid in existing:
  return None,[],[],{'kind':'homepage','id':sid,'status':'skipped','reason':'Already in original catalog'}
 async with sem:
  page=None
  try:
   page,title,clicked=await open_browser(browser,row['url'])
   first=await screenshot(page,0)
   if variation(first)<14:raise ValueError("Low-contrast or blank hero screenshot")
   # Capture a genuine second viewport; reject lookalikes instead of making a fake region.
   second=None
   height=await page.evaluate('document.documentElement.scrollHeight')
   if height>1650:
    second=await screenshot(page,850)
    difference=max(ImageStat.Stat(ImageChops.difference(first.resize((96,64)),second.resize((96,64)))).mean)
    if variation(second)<11 or difference<8:second=None
   site=dict(id=sid,name=row['name'],sector=row['sector'],focus=row['focus'],model=row['model'],
        url=row['url'],domain=re.sub(r'^www\.','',re.sub(r'^https?://','',row['url']).split('/')[0]),
        summary=row['summary'],takeaway=row['takeaway'],palette='neutral',
        featured=False,curation_batch='v21-staged')
   store(first,SHOT/'sites'/(sid+'.webp'))
   note,mod=note_module(sid,sid+'-hero',row['hc'],row['ht'],row['hl'],row['summary'],page.url,first)
   notes=[note];mods=[mod]
   if second is not None:
    n,m=note_module(sid,sid+'-detail',row['dc'],row['dt'],row['dl'],row['summary'],page.url,second)
    notes.append(n);mods.append(m)
   print('HOME_OK',sid,len(mods),'consent',clicked,flush=True)
   return site,notes,mods,dict(kind='homepage',id=sid,status='captured',source_url=page.url,title=title,
         sections=len(mods),cookie_clicked=clicked,visual_variation=round(variation(first),1))
  except Exception as e:
   print('HOME_REJECT',sid,str(e)[:150],flush=True)
   return None,[],[],dict(kind='homepage',id=sid,status='rejected',source_url=row['url'],reason=str(e)[:250])
  finally:
   if page:await page.close()
async def deep_capture(browser,sem,row,eligible):
 sid=row['site_id'];nid=sid+'-'+row['slug']
 if sid not in eligible:
  return None,None,dict(kind='inner-page',id=nid,status='skipped',reason='Parent site not validated')
 async with sem:
  page=None
  try:
   page,title,clicked=await open_browser(browser,row['url'])
   im=await screenshot(page,0)
   if variation(im)<13:raise ValueError('Blank or low-information inner page')
   note,mod=note_module(sid,nid,row['category'],row['title'],row['lesson'],row['summary'],page.url,im)
   print('DEEP_OK',nid,row['category'],flush=True)
   return note,mod,dict(kind='inner-page',id=nid,status='captured',source_url=page.url,
       title=title,category=row['category'],cookie_clicked=clicked)
  except Exception as e:
   print('DEEP_REJECT',nid,str(e)[:160],flush=True)
   return None,None,dict(kind='inner-page',id=nid,status='rejected',source_url=row['url'],reason=str(e)[:240])
  finally:
   if page:await page.close()
def sheet(ids,kind,title):
 cols=4;cellw,cellh=290,228
 rows=(len(ids)+cols-1)//cols
 canvas=Image.new('RGB',(cols*cellw,rows*cellh+28),BG)
 d=ImageDraw.Draw(canvas)
 for i,name in enumerate(ids):
  source=SHOT/('sites' if kind=='sites' else 'modules')/(name+'.webp')
  if not source.exists():continue
  with Image.open(source) as inp:
   pic=inp.convert('RGB');pic.thumbnail((272,192))
  x=(i%cols)*cellw+10;y=(i//cols)*cellh+9
  canvas.paste(pic,(x,y));d.text((x,y+195),name[:38],fill='#111')
 canvas.save(OUT/(title+'.jpg'),'JPEG',quality=82,optimize=True)
async def main():
 OUT.mkdir(parents=True,exist_ok=True)
 sourcefile=ROOT/'app/source_index.json'
 modulesfile=ROOT/'app/module_catalog.json'
 data=json.loads(sourcefile.read_text());mods=json.loads(modulesfile.read_text())
 existing={x['id'] for x in data['sites']}
 existing_notes={x['id'] for x in data['notes']}
 existing_mods={x['id'] for x in mods}
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,channel='chrome',args=['--no-sandbox','--disable-dev-shm-usage'])
  sem=asyncio.Semaphore(3)
  home=await asyncio.gather(*(home_capture(browser,sem,row,existing) for row in CONF['sites']))
  approved=[x[0]['id'] for x in home if x[0]]
  eligible=existing|set(approved)
  deep=await asyncio.gather(*(deep_capture(browser,sem,row,eligible) for row in CONF['deep_pages']))
  await browser.close()
 sites=[x[0] for x in home if x[0]]
 notes=[n for x in home for n in x[1]]+[x[0] for x in deep if x[0]]
 newmods=[m for x in home for m in x[2]]+[x[1] for x in deep if x[1]]
 # Generated IDs are unique. Never overwrite an existing canonical section.
 assert len({n['id'] for n in notes})==len(notes)
 assert len({m['id'] for m in newmods})==len(newmods)
 assert not (set(n['id'] for n in notes)&existing_notes)
 assert not (set(m['id'] for m in newmods)&existing_mods)
 data['sites']=sites+data['sites']
 data['notes']=notes+data['notes']
 mods=newmods+mods
 sourcefile.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
 modulesfile.write_text(json.dumps(mods,indent=2,ensure_ascii=False)+'\n')
 audits=[x[3] for x in home]+[x[2] for x in deep]
 result=dict(batch='v21',captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
   sites_attempted=len(CONF['sites']),sites_captured=len(sites),inner_attempted=len(CONF['deep_pages']),
   inner_captured=sum(x[0] is not None for x in deep),modules_added=len(newmods),
   accepted_sites=approved,accepted_module_ids=[m['id'] for m in newmods],
   total_sites=len(data['sites']),total_modules=len(mods),audits=audits)
 (OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 sheet(approved,'sites','new-site-contact-sheet')
 sheet([m['id'] for m in newmods],'modules','new-section-contact-sheet')
 print('FINAL_AUDIT',json.dumps({k:result[k] for k in ['sites_attempted','sites_captured','inner_attempted','inner_captured','modules_added','total_sites','total_modules','accepted_sites']},ensure_ascii=False),flush=True)
 if len(approved)<7:raise SystemExit('Too few real verified companies; do not stage a broken batch.')
 if result['inner_captured']<9:raise SystemExit('Too few actual inner pages; do not stage a broken batch.')
if __name__=='__main__':asyncio.run(main())
