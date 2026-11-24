#!/usr/bin/env python3
"""Curated Atlas V1.9 catalog expansion. Capture real pages, never synthesize visuals.

Run from extracted source with the repo's tracked screenshots folder present.
Only browser-verified successful captures enter source_index.json.
"""
from __future__ import annotations
import asyncio, datetime, io, json, re, shutil
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageStat, ImageChops
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
SCREENS=ROOT/'screenshots'
OUT=SCREENS/'research-v19'
AUDIT=[]
STAMP=datetime.datetime.now(datetime.timezone.utc).isoformat()
# Company, sector, specific visual learning objective; actual source URLs vetted separately.
# Each site has independent editorial notes for its opening section and its real below-fold region.
CANDIDATES=[
("q-industrial","Q Industrial","Industrial Materials","Coatings with immersive 3D branding","Industrial coatings","https://www.q-industrial.com/en-de","Paint and coating systems paired with immersive material-focused brand storytelling.","A large 3D identity can coexist with a navigable B2B product architecture.","Hero","Industrial brand as visual system","A graphic identity makes industrial material science memorable.","Products","Industrial coatings product discovery","Industry and surface filters preserve specification-oriented entry points."),
("cly-del","Cly-Del","Manufacturing","Precision metal stamping","Deep drawing and tooling","https://cly-del.com/","Precision drawn and stamped parts explained through light engineering illustration and craft.","Balance reassuring manufacturing heritage with distinctive illustrative art direction.","Hero","Technical illustration-driven hero","A restrained visual language gives tiny industrial components prominence.","Capabilities","High-precision manufacturing proof","Detailed production capabilities support technical confidence."),
("intrepid-automation","Intrepid Automation","Manufacturing","Digital casting technology","Automated manufacturing","https://www.intrepidautomation.com/","Advanced casting machines with high-contrast industrial photography and a strong technology narrative.","Make manufacturing machinery feel cinematic without hiding production use.","Hero","Dark cinematic industrial hardware","Large machinery imagery establishes a clear first impression.","Technology","Digital casting solutions","Technology storytelling builds demand for a new manufacturing process."),
("terminal-industries","Terminal Industries","Logistics Technology","AI-native yard operating system","Enterprise logistics platform","https://terminal-industries.com/","Computer vision and yard automation explained through interactive logistics workflows.","Turn invisible industrial software into an engaging visual system.","Hero","Operational software storytelling","A bold technical product concept makes yard automation tangible.","Process","Gate-to-dock workflow narrative","Real logistics workflow steps connect digital features to operations."),
("lumafield","Lumafield","Industrial Technology","Industrial CT and inspection","Engineering inspection platform","https://www.lumafield.com/","CT scanners and 3D inspection software with object-slice imagery and bold product visuals.","Use the product's own data visualization as the brand's graphic language.","Hero","CT scanning as brand art direction","Industrial scan imagery communicates invisible product insight.","Products","Scanner and platform architecture","Hardware and browser-based analysis are clearly separated."),
("caracol-am","Caracol AM","Manufacturing","Large-format robotic additive manufacturing","Robotic advanced manufacturing","https://www.caracol-am.com/","Large-format robotic 3D printing uses strong typography, dark imagery and physical scale.","Use industrial-scale process imagery as a confident visual signature.","Hero","Large-format industrial production","Product scale and bold words communicate process differentiation.","Applications","Advanced manufacturing applications","Sector-led examples connect complex technology to real use."),
("sevenloop","Sevenloop","Manufacturing","AI-assisted build-to-print precision manufacturing","Contract manufacturing","https://www.sevenloop.org/","An advanced manufacturing provider using white-space and high-fidelity parts photography.","Combine a restrained UI with detailed engineered-product visuals.","Hero","Product render on minimalist canvas","Technical parts carry the brand story without visual clutter.","Process","Build-to-print workflow","The buying process moves from engineering specifications into production."),
("carbo-tech","CARBO","Industrial Materials","Ceramic proppant materials","Advanced industrial materials","https://carbo.tech/","Ceramic industrial materials conveyed through 3D visuals and specific product applications.","Make a microscopic technical product understandable with materials-focused 3D.","Hero","Microscopic industrial material narrative","3D material behavior translates invisible performance.","Products","Ceramic material portfolio","Application-first navigation supports technical buyer evaluation."),
("hadrian","Hadrian","Manufacturing","Advanced automated precision factories","Aerospace manufacturing","https://www.hadrian.co/","Factory automation and high-precision manufacturing introduced through bold type and industrial footage.","Strong photographic rhythm can convey modern production confidence.","Hero","Future of factories brand statement","A bold manufacturing mission sets the tone.","Capabilities","Digital factory operations","Factory process demonstrations substantiate the claim."),
("vention","Vention","Industrial Automation","Modular automation platform","Robot cell design platform","https://vention.com/","Industrial automation hardware, programming and simulation presented as a product platform.","Let interactive software and physical product visuals explain one system.","Hero","Robot cell design platform","Hardware and software are presented together as a usable product.","Products","Robotics product ecosystem","Buyers browse cells and hardware by deployment need."),
("machina-labs","Machina Labs","Manufacturing","AI-guided robotic metal forming","Advanced production cells","https://machinalabs.ai/","Robotic metal shaping uses industrial video and visually striking metal forms.","Use process visuals rather than generic technology promises.","Hero","Robotic metal fabrication","Industrial motion communicates new production capacity.","Capabilities","Robotics manufacturing workflow","Process explanation ties new technology to deliverable parts."),
("bright-machines","Bright Machines","Industrial Automation","AI manufacturing infrastructure","Robotics platform","https://www.brightmachines.com/","Automated factories and industrial AI presented through layered hardware and software.","Show a complex automation platform through product proof and process.","Hero","AI-enabled factory introduction","The opening combines equipment scale and software ambition.","Technology","Automation system stages","Integrated technology is articulated with operational proof."),
("carbon3d","Carbon","Manufacturing","Digital light synthesis 3D printing","Additive manufacturing platform","https://www.carbon3d.com/","Advanced 3D printing uses design-led consumer products to prove industrial relevance.","Concrete manufactured outcomes demonstrate what the process enables.","Hero","Additive technology hero","Production product photography reduces process abstraction.","Products","Hardware materials software system","The technical stack becomes legible through product navigation."),
("biomason","Biomason","Industrial Materials","Biofabricated cement","Sustainable materials","https://biomason.com/","Biocement production and biotechnology introduced through tactile material photography.","Use material texture as the emotional proof of a climate technology.","Hero","Biomaterial storytelling","Physical material textures express a new manufacturing process.","Process","Biocement production","Explained process stages show how biology becomes a material."),
("zahner","Zahner","Architecture & Materials","Custom architectural metal engineering","Architecture fabrication","https://azahner.com/","Architectural metalwork shown through monumental project photography and detailed engineering.","Combine a project-led portfolio with material-specification depth.","Projects","Architectural metal showcase","Fabrication photography elevates technical materials into design.","Capabilities","Custom engineered metal systems","Capabilities turn aesthetic ambition into buildable detail."),
("primeasia-leather","PrimeAsia Leather","Industrial Materials","Premium leather manufacturing","Tannery materials","https://www.primeasialeather.com/","Large-scale leather production balanced with material and editorial visuals.","Present a tactile B2B commodity as a curated material library.","Hero","Tactile materials identity","Leather finish and texture become the design language.","Products","Material collections","Material variety is organized for brand and procurement teams."),
("iem","IEM","Industrial Technology","Electrical power distribution equipment","Electrical manufacturing","https://www.iemfg.com/","Power distribution equipment introduced through high-end industrial art direction.","A consumer-grade product presentation improves a technical B2B catalog.","Hero","Power equipment visual identity","Industrial hardware photography makes the offer visible.","Products","Electrical system navigation","Product routes support engineered equipment specification."),
("novanta-photonics","Novanta Photonics","Industrial Technology","Photonics and laser components","Precision laser manufacturing","https://novantaphotonics.com/","Lasers and photonics hardware organized by technology and industrial application.","Balance high-end scientific imagery with precise technical navigation.","Hero","Photonics innovation introduction","Precision optics provide distinctive brand imagery.","Products","Laser system families","Engineer-facing product architecture supports specification research."),
("boxo","BOXO","Modular Construction","Modular buildings and spaces","Prefabricated construction","https://boxo.com.ua/","Modular construction projects presented through large-scale architecture photography.","Allow finished construction projects to explain a flexible manufacturing offer.","Hero","Prefabricated building imagery","Strong project photography communicates flexible spatial design.","Projects","Modular construction project gallery","Diverse built environments demonstrate repeatable systems."),
("oneprom","OnePROM","Industrial Engineering","Industrial engineering in motion","Engineering services","https://oneprom.ru/","Industrial engineering brand known for motion-led typography and storytelling.","Use large type and movement to give heavy industry a distinctive identity.","Hero","Industrial engineering motion system","Typographic movement communicates the industrial personality.","Process","Engineering production narrative","Operational capabilities retain hierarchy under art direction."),
("sopo","SOPO","Industrial Components","Wound rotor and stator components","Electromechanical manufacturing","https://www.sopous.com/","Dark red industrial identity features a hero graphic built from winding components.","Let a real manufactured component define the visual brand.","Hero","Electromechanical component hero","One industrial object creates a strong graphic opening.","Products","Rotors and coils product structure","Engineering component families guide technical procurement."),
("kovo-haken","Kovo Haken","Manufacturing","Metalworking and fabrication","Metal manufacturing","https://kovohaken.cz/","Award-listed manufacturing site with a strong contemporary metalworking identity.","Express specialist fabrication through a differentiated visual identity.","Hero","Steel fabrication positioning","Metalworking identity combines craft and industrial rigor.","Capabilities","Fabrication services","Capability structure leads to buyer qualification."),
("magon-sistemi","Magon Sistemi","Architecture & Materials","Architectural construction systems","Building systems manufacturer","https://magonsistemi.it/","Construction systems presented with unusually refined architectural art direction.","Give building components a clear design-oriented showcase.","Hero","Architectural building systems","Product-as-architecture imagery establishes relevance.","Products","Construction systems discovery","A design-led product taxonomy supports specifiers."),
("kvadrat","Kvadrat","Design Materials","Architectural textiles and acoustics","Contract textiles manufacturer","https://www.kvadrat.dk/en/","High-performance textiles, color studies and collaborations with designers.","Use texture, color and photography as a sophisticated product-search language.","Hero","Premium textile art direction","Product texture creates a memorable brand language.","Products","Commercial textile discovery","Material browsing serves architects and specifiers."),
("snohetta","Snøhetta","Architecture & Design","Transdisciplinary architecture and design","Design consultancy","https://www.snohetta.com/","Architecture, landscape, interiors and industrial design communicated through iconic projects.","Project-led, editorial composition can replace generic agency claims.","Projects","Architecture and landscape visual archive","Large projects express the studio's capabilities.","Approach","Transdisciplinary design approach","The studio's services make sense through client outcomes."),
("big-architects","BIG","Architecture & Design","Contemporary architecture projects","Architectural services","https://big.dk/","Global architecture firm known for image-led project browsing and unusual project taxonomy.","Let building photography shape a portfolio's visual rhythm.","Projects","Dense project archive","Project-rich grids support exploration without a brochure structure.","Approach","Architecture practice and process","Design principles connect diverse projects."),
("layer-design","LAYER","Product Design","Industrial design studio","Product design consultancy","https://layerdesign.com/","High-concept physical product design presented as immersive portfolio work.","Use close-up product photography to differentiate a design consultancy.","Projects","Industrial design portfolio","Products are treated as hero objects.","Capabilities","Product strategy and industrial design","A clear service proposition sits beneath striking objects."),
("form-us-with-love","Form Us With Love","Product Design","Furniture and industrial design","Design consultancy","https://www.formuswithlove.se/","Stockholm industrial design studio with a distinctive object-focused portfolio.","Use the object as the primary visual hierarchy rather than many service cards.","Projects","Furniture and product projects","Material, shape and detail carry the design argument.","Approach","Design partnership","Research and production sit alongside expressive product imagery."),
("vola","VOLA","Design Materials","Architectural tapware and fittings","Architectural product manufacturer","https://en.vola.com/","Danish architectural fittings emphasize geometry, restraint and craft.","Minimalist product imagery gives a technical object emotional value.","Hero","Architectural product clarity","Single-object storytelling creates premium visual recognition.","Products","Fittings and finishes","Product specification remains available beneath a clean identity."),
("rockfon","Rockfon","Design Materials","Architectural acoustic ceiling systems","Architectural materials supplier","https://www.rockfon.com/en-us/","Stone-wool acoustic solutions presented through real architectural environments.","Blend built-project photography with specification-led product discovery.","Hero","Architectural acoustic spaces","Project photography expresses a technical material benefit.","Products","Ceiling product systems","Specifiers access product families and acoustical performance."),
("attio","Attio","Enterprise Software","Modern CRM system","B2B CRM SaaS","https://attio.com/","Highly polished CRM product visuals, precise type hierarchy and purposeful interactions.","Study product-UI-first storytelling with consistent visual systems.","Hero","Product-centric software introduction","A strong app UI previews the value immediately.","Products","CRM workflows","Workflow imagery organizes the sales platform."),
("clay","Clay","Enterprise Software","Sales data and enrichment platform","B2B GTM software","https://www.clay.com/","B2B data workflows expressed using an unusual friendly and modular graphic language.","Use distinctive illustration and product demos without obscuring function.","Hero","Playful B2B product identity","A memorable graphic system differentiates technical software.","Process","GTM workflow demonstrations","Real product sequences support evaluation."),
("mercury","Mercury","Enterprise Software","Business banking platform","Fintech B2B","https://mercury.com/","Business finance product with editorial graphic language and polished app previews.","Make a serious financial product approachable without sacrificing trust.","Hero","Finance interface as brand","A distinct graphic language introduces business workflows.","Products","Financial product system","Product UI and trust proof guide business buyers."),
("ramp","Ramp","Enterprise Software","Corporate finance operations","Fintech B2B","https://ramp.com/","Spend management product uses balanced layout, expressive data and clear value propositions.","Connect a strong product identity to measurable operational outcomes.","Hero","Spend management product intro","Interface-led proof grounds the financial proposition.","Capabilities","Financial operations platform","A multi-product system is grouped around practical tasks."),
("retool","Retool","Enterprise Software","Internal tools and workflow software","Developer platform","https://retool.com/","Developer tool product visuals with a direct, compositionally varied enterprise site.","Mix real interface captures with technical use cases and proof.","Hero","Internal tool builder proposition","The product itself anchors the pitch.","Products","App building modules","Developers find product functions by workflow."),
]

CHALLENGE=re.compile(r'access denied|just a moment|checking your browser|robot check|verify you are human|enable javascript|captcha|forbidden|please enable cookies',re.I)
COOKIE=[
  re.compile(r'^(reject (all|optional)|decline (all|optional)|necessary only|only necessary|essential only|use necessary cookies only|allow necessary only|reject all cookies)$',re.I),
  re.compile(r'^(accept all|allow all|accept cookies|accept all cookies|accept|agree|got it|ok)$',re.I)
]
def rms(image):
    im=image.resize((96,64)).convert('RGB')
    st=ImageStat.Stat(im)
    return max(st.stddev)
def save_img(image,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    image.convert('RGB').save(path,'WEBP',quality=83,method=5)
def mk_meta(row):
    (ident,name,sector,focus,model,url,summary,takeaway,*_)=row
    return dict(id=ident,name=name,sector=sector,focus=focus,model=model,
        url=url,domain=urlparse(url).hostname.removeprefix('www.'),
        summary=summary,takeaway=takeaway,palette='neutral',featured=False)

async def dismiss(page):
    try:
      for _ in range(2):
        for frame in page.frames:
          for pattern in COOKIE:
            try:
              button=frame.get_by_role('button',name=pattern).first
              if await button.count() and await button.is_visible(timeout=700):
                await button.click(timeout=1700);await page.wait_for_timeout(650);return
            except Exception:pass
        await page.wait_for_timeout(450)
    except Exception:pass

async def screenshot(page):
    await page.evaluate("""async()=>{document.querySelectorAll('img[loading="lazy"]').forEach(x=>x.loading='eager');try{await document.fonts.ready}catch(e){}}""")
    await page.wait_for_timeout(650)
    return Image.open(io.BytesIO(await page.screenshot(type='png',full_page=False,animations='disabled',timeout=12000))).convert('RGB')

async def capture_one(browser,sem,row):
    ident=row[0];url=row[5]
    async with sem:
      page=await browser.new_page(viewport={'width':1440,'height':920},
          device_scale_factor=1,locale='en-US',color_scheme='light')
      try:
        resp=await page.goto(url,wait_until='domcontentloaded',timeout=26000)
        if not resp or resp.status>=400:raise RuntimeError('HTTP '+str(resp.status if resp else 'no response'))
        await page.wait_for_timeout(1100)
        title=(await page.title())[:140]
        body=(await page.locator('body').inner_text(timeout=5000))[:2500]
        if CHALLENGE.search(title+' '+body[:450]):raise RuntimeError('Bot challenge / access denied')
        if len(body.strip())<110:raise RuntimeError('Too little visible text for a quality design reference')
        await dismiss(page)
        await page.keyboard.press('Escape')
        await page.mouse.move(1400,895)
        top=await screenshot(page)
        if rms(top)<12:raise RuntimeError('Blank or low-information opening screenshot')
        source_file=SCREENS/'sites'/(ident+'.webp')
        save_img(top,source_file)
        approved=[dict(id=ident,kind='website',url=url,resolved_url=page.url,title=title,status='captured',image_file=str(source_file.relative_to(ROOT)),contrast=round(rms(top),1))]
        # A note is a genuine crop of a browser screenshot; no generated mockup.
        notes=[];mods=[]
        for suffix,category,section_title,lesson,y0,y1 in [('hero',row[8],row[9],row[10],105,790)]:
          nid=ident+'-'+suffix
          path=SCREENS/'notes'/(nid+'.webp')
          save_img(top,path)
          notes.append(dict(id=nid,site_id=ident,type=category,title=section_title,
             pattern=category+' study',url=url,summary=row[6],lesson=lesson))
          crop=top.crop((0,y0,1440,y1))
          cid=nid
          dest=SCREENS/'modules'/(cid+'.webp')
          save_img(crop,dest)
          mods.append(dict(id=cid,site_id=ident,page_id=nid,
            category=category,type=category,title=section_title,
            lesson=lesson,summary=row[6],url=url,
            source_capture='/screenshots/notes/'+nid+'.webp',
            image_file=cid+'.webp',crop_px=[0,y0,1440,y1],
            reference_type='Real website — browser crop'))
        # Capture an actual below-fold segment only if a sufficiently long, changed page exists.
        height=await page.evaluate('document.documentElement.scrollHeight')
        if height>1520:
          await page.evaluate('window.scrollTo({top:850,behavior:"instant"})')
          await page.wait_for_timeout(900)
          lower=await screenshot(page)
          delta=ImageStat.Stat(ImageChops.difference(top.resize((96,64)),lower.resize((96,64)))).mean
          if rms(lower)>=11 and max(delta)>9:
            suffix='detail';nid=ident+'-'+suffix
            dest=SCREENS/'notes'/(nid+'.webp')
            save_img(lower,dest)
            notes.append(dict(id=nid,site_id=ident,type=row[11],title=row[12],
                pattern=row[11]+' study',url=url,summary=row[6],lesson=row[13]))
            y0,y1=90,810
            crop=lower.crop((0,y0,1440,y1))
            save_img(crop,SCREENS/'modules'/(nid+'.webp'))
            mods.append(dict(id=nid,site_id=ident,page_id=nid,
                category=row[11],type=row[11],title=row[12],
                lesson=row[13],summary=row[6],url=url,
                source_capture='/screenshots/notes/'+nid+'.webp',
                image_file=nid+'.webp',crop_px=[0,y0,1440,y1],
                reference_type='Real website — browser crop'))
            approved.append(dict(id=nid,kind='below-fold section',status='captured',scroll=850,pixel_difference=round(max(delta),1)))
        print('CAPTURED',ident,'sections',len(mods),'title',title[:60],flush=True)
        return (mk_meta(row),notes,mods,approved)
      except Exception as e:
        print('REJECTED',ident,str(e)[:140],flush=True)
        return (None,[],[],[dict(id=ident,status='rejected',url=url,reason=str(e)[:180])])
      finally:
        await page.close()

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog_path=ROOT/'app/source_index.json'
    module_path=ROOT/'app/module_catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    existing={x['id'] for x in catalog['sites']}
    candidates=[r for r in CANDIDATES if r[0] not in existing]
    async with async_playwright() as p:
      browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
      sem=asyncio.Semaphore(3)
      results=await asyncio.gather(*(capture_one(browser,sem,row) for row in candidates))
      await browser.close()
    sites=[x[0] for x in results if x[0]]
    notes=[n for x in results for n in x[1]]
    mods=[m for x in results for m in x[2]]
    audit=[a for x in results for a in x[3]]
    catalog['sites'].extend(sites);catalog['notes'].extend(notes)
    catalog['checked_at']=STAMP[:10]
    previous=json.loads(module_path.read_text(encoding='utf-8'))
    slugs={x['id'] for x in previous}
    previous.extend(x for x in mods if x['id'] not in slugs)
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    module_path.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report=dict(created_at=STAMP,attempted=len(candidates),accepted=len(sites),rejected=len(candidates)-len(sites),
       new_notes=len(notes),new_modules=len(mods),total_sites=len(catalog['sites']),
       total_modules=len(previous),approved=[x['id'] for x in sites],results=audit)
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Produce a small review contact sheet, showing genuine captures only.
    if sites:
      from PIL import ImageDraw
      W=1180;thumb=(276,200);cols=4;rows=(len(sites)+3)//4
      sheet=Image.new('RGB',(W,rows*236+18),'#f5f5f5')
      draw=ImageDraw.Draw(sheet)
      for i,entry in enumerate(sites):
        src=Image.open(SCREENS/'sites'/(entry['id']+'.webp')).convert('RGB')
        src.thumbnail(thumb)
        x=10+(i%cols)*294;y=12+(i//cols)*236
        sheet.paste(src,(x,y))
        draw.text((x,y+203),entry['name'],fill='#111111')
      sheet.save(OUT/'contact-sheet.jpg',format='JPEG',quality=81,optimize=True)
    print('REPORT',json.dumps({k:report[k] for k in ['attempted','accepted','rejected','new_notes','new_modules','total_sites','total_modules','approved']},ensure_ascii=False),flush=True)
    # Require meaningful growth; reject a broken batch rather than silently publish 1 or 2.
    if len(sites)<12:raise SystemExit('Too few approved captures for V2.0; do not publish.')
if __name__=='__main__':asyncio.run(main())
,re.I),
  re.compile(r'^(accept all|allow all|accept cookies|accept all cookies|accept|agree|got it|ok)$',re.I)
]
def rms(image):
    im=image.resize((96,64)).convert('RGB')
    st=ImageStat.Stat(im)
    return max(st.stddev)
def save_img(image,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    image.convert('RGB').save(path,'WEBP',quality=83,method=5)
def mk_meta(row):
    (ident,name,sector,focus,model,url,summary,takeaway,*_)=row
    return dict(id=ident,name=name,sector=sector,focus=focus,model=model,
        url=url,domain=urlparse(url).hostname.removeprefix('www.'),
        summary=summary,takeaway=takeaway,palette='neutral',featured=False)

async def dismiss(page):
    try:
      for _ in range(2):
        for frame in page.frames:
          for pattern in COOKIE:
            try:
              button=frame.get_by_role('button',name=pattern).first
              if await button.count() and await button.is_visible(timeout=700):
                await button.click(timeout=1700);await page.wait_for_timeout(300);return
            except Exception:pass
        await page.wait_for_timeout(450)
    except Exception:pass

async def screenshot(page):
    await page.evaluate("""async()=>{document.querySelectorAll('img[loading="lazy"]').forEach(x=>x.loading='eager');try{await document.fonts.ready}catch(e){}}""")
    await page.wait_for_timeout(650)
    return Image.open(io.BytesIO(await page.screenshot(type='png',full_page=False,animations='disabled',timeout=12000))).convert('RGB')

async def capture_one(browser,sem,row):
    ident=row[0];url=row[5]
    async with sem:
      page=await browser.new_page(viewport={'width':1440,'height':920},
          device_scale_factor=1,locale='en-US',color_scheme='light')
      try:
        resp=await page.goto(url,wait_until='domcontentloaded',timeout=26000)
        if not resp or resp.status>=400:raise RuntimeError('HTTP '+str(resp.status if resp else 'no response'))
        await page.wait_for_timeout(1100)
        title=(await page.title())[:140]
        body=(await page.locator('body').inner_text(timeout=5000))[:2500]
        if CHALLENGE.search(title+' '+body[:450]):raise RuntimeError('Bot challenge / access denied')
        if len(body.strip())<110:raise RuntimeError('Too little visible text for a quality design reference')
        await dismiss(page)
        top=await screenshot(page)
        if rms(top)<12:raise RuntimeError('Blank or low-information opening screenshot')
        source_file=SCREENS/'sites'/(ident+'.webp')
        save_img(top,source_file)
        approved=[dict(id=ident,kind='website',url=url,resolved_url=page.url,title=title,status='captured',image_file=str(source_file.relative_to(ROOT)),contrast=round(rms(top),1))]
        # A note is a genuine crop of a browser screenshot; no generated mockup.
        notes=[];mods=[]
        for suffix,category,section_title,lesson,y0,y1 in [('hero',row[8],row[9],row[10],105,790)]:
          nid=ident+'-'+suffix
          path=SCREENS/'notes'/(nid+'.webp')
          save_img(top,path)
          notes.append(dict(id=nid,site_id=ident,type=category,title=section_title,
             pattern=category+' study',url=url,summary=row[6],lesson=lesson))
          crop=top.crop((0,y0,1440,y1))
          cid=nid
          dest=SCREENS/'modules'/(cid+'.webp')
          save_img(crop,dest)
          mods.append(dict(id=cid,site_id=ident,page_id=nid,
            category=category,type=category,title=section_title,
            lesson=lesson,summary=row[6],url=url,
            source_capture='/screenshots/notes/'+nid+'.webp',
            image_file=cid+'.webp',crop_px=[0,y0,1440,y1],
            reference_type='Real website — browser crop'))
        # Capture an actual below-fold segment only if a sufficiently long, changed page exists.
        height=await page.evaluate('document.documentElement.scrollHeight')
        if height>1520:
          await page.evaluate('window.scrollTo({top:850,behavior:"instant"})')
          await page.wait_for_timeout(900)
          lower=await screenshot(page)
          delta=ImageStat.Stat(ImageChops.difference(top.resize((96,64)),lower.resize((96,64)))).mean
          if rms(lower)>=11 and max(delta)>9:
            suffix='detail';nid=ident+'-'+suffix
            dest=SCREENS/'notes'/(nid+'.webp')
            save_img(lower,dest)
            notes.append(dict(id=nid,site_id=ident,type=row[11],title=row[12],
                pattern=row[11]+' study',url=url,summary=row[6],lesson=row[13]))
            y0,y1=90,810
            crop=lower.crop((0,y0,1440,y1))
            save_img(crop,SCREENS/'modules'/(nid+'.webp'))
            mods.append(dict(id=nid,site_id=ident,page_id=nid,
                category=row[11],type=row[11],title=row[12],
                lesson=row[13],summary=row[6],url=url,
                source_capture='/screenshots/notes/'+nid+'.webp',
                image_file=nid+'.webp',crop_px=[0,y0,1440,y1],
                reference_type='Real website — browser crop'))
            approved.append(dict(id=nid,kind='below-fold section',status='captured',scroll=850,pixel_difference=round(max(delta),1)))
        print('CAPTURED',ident,'sections',len(mods),'title',title[:60],flush=True)
        return (mk_meta(row),notes,mods,approved)
      except Exception as e:
        print('REJECTED',ident,str(e)[:140],flush=True)
        return (None,[],[],[dict(id=ident,status='rejected',url=url,reason=str(e)[:180])])
      finally:
        await page.close()

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog_path=ROOT/'app/source_index.json'
    module_path=ROOT/'app/module_catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    existing={x['id'] for x in catalog['sites']}
    candidates=[r for r in CANDIDATES if r[0] not in existing]
    async with async_playwright() as p:
      browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
      sem=asyncio.Semaphore(3)
      results=await asyncio.gather(*(capture_one(browser,sem,row) for row in candidates))
      await browser.close()
    sites=[x[0] for x in results if x[0]]
    notes=[n for x in results for n in x[1]]
    mods=[m for x in results for m in x[2]]
    audit=[a for x in results for a in x[3]]
    catalog['sites'].extend(sites);catalog['notes'].extend(notes)
    catalog['checked_at']=STAMP[:10]
    previous=json.loads(module_path.read_text(encoding='utf-8'))
    slugs={x['id'] for x in previous}
    previous.extend(x for x in mods if x['id'] not in slugs)
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    module_path.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report=dict(created_at=STAMP,attempted=len(candidates),accepted=len(sites),rejected=len(candidates)-len(sites),
       new_notes=len(notes),new_modules=len(mods),total_sites=len(catalog['sites']),
       total_modules=len(previous),approved=[x['id'] for x in sites],results=audit)
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Produce a small review contact sheet, showing genuine captures only.
    if sites:
      from PIL import ImageDraw
      W=1180;thumb=(276,200);cols=4;rows=(len(sites)+3)//4
      sheet=Image.new('RGB',(W,rows*236+18),'#f5f5f5')
      draw=ImageDraw.Draw(sheet)
      for i,entry in enumerate(sites):
        src=Image.open(SCREENS/'sites'/(entry['id']+'.webp')).convert('RGB')
        src.thumbnail(thumb)
        x=10+(i%cols)*294;y=12+(i//cols)*236
        sheet.paste(src,(x,y))
        draw.text((x,y+203),entry['name'],fill='#111111')
      sheet.save(OUT/'contact-sheet.jpg',format='JPEG',quality=81,optimize=True)
    print('REPORT',json.dumps({k:report[k] for k in ['attempted','accepted','rejected','new_notes','new_modules','total_sites','total_modules','approved']},ensure_ascii=False),flush=True)
    # Require meaningful growth; reject a broken batch rather than silently publish 1 or 2.
    if len(sites)<12:raise SystemExit('Too few approved captures for V2.0; do not publish.')
if __name__=='__main__':asyncio.run(main())
