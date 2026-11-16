const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.ORI_PLAYWRIGHT_MODULE || path.join(process.env.TEMP,'ori-lote2-visual/node_modules/playwright'));
const baseURL=process.env.ORI_QA_BASE_URL || 'http://127.0.0.1:5176';
const phase=process.argv[2]||'antes',root='docs/evidencia/lote3';
const sizes=[[1440,900],[1280,800],[768,1024],[390,844],[360,740],[320,740]];
(async()=>{
 fs.mkdirSync(root,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.ORI_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const page=await browser.newPage();
 let estado='lista';
 const peticiones=[];
 await page.route('**/api/**',async r=>{
  peticiones.push(new URL(r.request().url()).pathname);
  if(estado==='carga')await new Promise(resolve=>setTimeout(resolve,2000));
  return r.fulfill(estado==='error'?{status:500,json:{detail:'Detalle privado ficticio'}}:{json:{items:estado==='vacio'?[]:[{codigo:'USB-ORI-2026-00007',aliado:'Universidad de cooperación e investigación internacional de ejemplo',tipo_convenio:'Marco de cooperación académica',objeto:'Cooperación para investigación, movilidad y formación conjunta.\nSe conserva la descripción completa con información de consulta pública.',fecha_inicio:'2026-01-01',fecha_vencimiento:'2028-01-01',estado:'VIGENTE'}],total:21}});
 });
 const results=[];
 for(const [width,height]of sizes){await page.setViewportSize({width,height});await page.goto(baseURL+'/directorio');await page.locator('tbody tr').waitFor();await page.evaluate(()=>document.fonts.ready);
 const m=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth,columns:document.querySelectorAll('thead th').length,region:document.querySelector('[role=region]').clientWidth}));results.push({width,height,...m});
 if(width===1440||width===390)await page.screenshot({path:`${root}/${phase}-directorio-${width}.png`,fullPage:true});
 if(phase==='despues'){if(m.page>width+1)throw Error('Page overflow '+width);const region=page.getByRole('region',{name:'Convenios vigentes'});await region.focus();await region.evaluate(e=>e.scrollLeft=e.scrollWidth);const a=await page.locator('tbody td').last().boundingBox(),b=await region.boundingBox();if(a.x+a.width>b.x+b.width+2)throw Error('Final column inaccessible');}
 }
 fs.writeFileSync(`${root}/${phase}-medidas.json`,JSON.stringify({browser:await browser.version(),syntheticData:true,results},null,2));
 const correos=[];
 if(phase==='despues'){
  await page.setViewportSize({width:390,height:844});
  for(const alterno of ['vacio','error','carga']){estado=alterno;await page.goto(baseURL+'/directorio');await page.getByRole(alterno==='error'?'alert':alterno==='carga'?'status':'contentinfo').waitFor();if(alterno==='vacio')await page.getByText('No hay convenios vigentes disponibles en este momento.').waitFor();await page.screenshot({path:`${root}/directorio-${alterno}-390.png`,fullPage:true});}
  if(peticiones.some(p=>p!=='/api/public/directorio-convenios'))throw Error('Unexpected private API request');
  for(const name of ['firma','contraparte','verificacion','recuperacion'])for(const [width,height]of sizes){await page.setViewportSize({width,height});await page.goto('about:blank');await page.setContent(fs.readFileSync(`${root}/correos/${name}.html`,'utf8'));if(!await page.getByText('ORI Manager',{exact:true}).isVisible())throw Error('Missing institutional header '+name);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);if(overflow)throw Error(`Email overflow ${name} ${width}`);await page.keyboard.press('Tab');const cta=page.getByRole('link');if(!await cta.isVisible())throw Error('CTA not visible');if(await page.evaluate(()=>document.activeElement?.tagName)!=='A')throw Error('CTA keyboard focus missing');correos.push({name,width,height,overflow});if(width===1440||width===390)await page.screenshot({path:`${root}/${name}-${width}.png`,fullPage:true});}
  fs.writeFileSync(`${root}/correos-medidas.json`,JSON.stringify(correos,null,2));
 }
 console.log(JSON.stringify({phase,results}));await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
