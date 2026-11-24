#!/usr/bin/env python3
"""Revisit staged V2.0 visual candidates with real browser behavior, never fake sources."""
import asyncio,io,json,os,re,datetime
from pathlib import Path
from PIL import Image,ImageStat,ImageChops,ImageDraw
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
SHOT=ROOT/'screenshots'
CANDIDATES=[
  ("q-industrial","https://www.q-industrial.com/en-de",["Don't accept","Reject all"],0,880),
  ("novanta-photonics","https://novantaphotonics.com/",["Okay","OK"],0,850),
  ("attio","https://attio.com/",["Reject"],0,900),
  ("clay","https://www.clay.com/",["Accept all"],0,850),
  ("primeasia-leather","https://www.primeasialeather.com/",[],560,1300),
  ("carbo-tech","https://carbo.tech/",[],600,1320),
]
def std(im):return max(ImageStat.Stat(im.resize((90,65)).convert('RGB')).stddev)
def save(im,path):path.parent.mkdir(parents=True,exist_ok=True);im.convert('RGB').save(path,'WEBP',quality=84,method=5)
async def shot(page):
  await page.evaluate("""async()=>{document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager');try{await document.fonts.ready;}catch(e){}}""")
  await page.wait_for_timeout(700)
  return Image.open(io.BytesIO(await page.screenshot(type='png',full_page=False,animations='disabled',timeout=15000))).convert('RGB')
async def capture(browser,row):
  sid,url,labels,scroll1,scroll2=row
  page=await browser.new_page(viewport={'width':1440,'height':920},device_scale_factor=1,locale='en-US',color_scheme='light')
  try:
    resp=await page.goto(url,wait_until='domcontentloaded',timeout=29000)
    if not resp or resp.status>=400:raise ValueError('HTTP '+str(resp.status if resp else 'none'))
    await page.wait_for_timeout(2600)
    clicked=None
    for wanted in labels:
      for frame in page.frames:
        try:
          el=frame.get_by_role('button',name=wanted,exact=True).first
          if await el.count() and await el.is_visible(timeout=650):
            await el.click(timeout=2500);clicked=wanted;break
        except Exception:pass
      if clicked:break
    if labels and not clicked:raise ValueError('Cannot close expected consent using its visible controls')
    await page.keyboard.press('Escape')
    await page.mouse.move(1405,885)
    await page.evaluate('(y)=>scrollTo({top:y,behavior:"instant"})',scroll1)
    await page.wait_for_timeout(2200)
    first=await shot(page)
    await page.evaluate('(y)=>scrollTo({top:y,behavior:"instant"})',scroll2)
    await page.wait_for_timeout(1100)
    second=await shot(page)
    if std(first)<17 or std(second)<12:raise ValueError('Insufficient screenshot visual content')
    delta=ImageStat.Stat(ImageChops.difference(first.resize((96,64)),second.resize((96,64)))).mean
    if max(delta)<9:raise ValueError('No distinct second section')
    save(first,SHOT/'sites'/(sid+'.webp'))
    save(first,SHOT/'notes'/(sid+'-hero.webp'))
    save(first.crop((0,105,1440,790)),SHOT/'modules'/(sid+'-hero.webp'))
    save(second,SHOT/'notes'/(sid+'-detail.webp'))
    save(second.crop((0,90,1440,810)),SHOT/'modules'/(sid+'-detail.webp'))
    print('RECUT_OK',sid,'clicked',clicked,'std',round(std(first),1),'delta',round(max(delta),1),flush=True)
    return {'id':sid,'status':'recaptured','clicked':clicked,'first_scroll':scroll1,'delta':round(max(delta),1)}
  except Exception as e:
    print('RECUT_SKIP',sid,str(e)[:150],flush=True)
    return {'id':sid,'status':'skipped','reason':str(e)[:300]}
  finally: await page.close()
async def main():
  async with async_playwright() as p:
    browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    results=await asyncio.gather(*(capture(browser,row) for row in CANDIDATES))
    await browser.close()
  out=SHOT/'research-v20'
  out.mkdir(exist_ok=True,parents=True)
  (out/'recapture-report.json').write_text(json.dumps(results,indent=2)+'\n')
  audit=json.loads((out/'audit.json').read_text())
  ids=audit['approved']
  sheet=Image.new('RGB',(1180,((len(ids)+3)//4)*236+18),'#f5f5f5')
  dr=ImageDraw.Draw(sheet)
  for i,sid in enumerate(ids):
    with Image.open(SHOT/'sites'/(sid+'.webp')) as im:
      v=im.convert('RGB');v.thumbnail((276,200))
      x=10+(i%4)*294;y=12+(i//4)*236
      sheet.paste(v,(x,y))
      dr.text((x,y+203),sid,fill='#111')
  sheet.save(out/'contact-sheet.jpg',format='JPEG',quality=83,optimize=True)
  print('RECUT_REPORT',json.dumps(results),flush=True)
if __name__=='__main__':asyncio.run(main())
