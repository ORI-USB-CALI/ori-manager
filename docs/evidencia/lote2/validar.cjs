const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.ORI_PLAYWRIGHT_MODULE || path.join(process.env.TEMP, 'ori-lote2-visual/node_modules/playwright'));
const baseURL = process.env.ORI_QA_BASE_URL || 'http://127.0.0.1:5174';
const phase = process.argv[2] || 'antes';
const root = 'docs/evidencia/lote2';
const persona = { id: 7, nombre_completo: 'Responsable de cooperación académica internacional y movilidad universitaria', correo: 'responsable.cooperacion.internacional.extenso@universidad-ejemplo.edu.co' };
const objeto = 'Convenio de cooperación para investigación, movilidad académica y formación conjunta con participación de las facultades y programas de ambas instituciones.\nSe conserva el objeto completo, incluyendo esta segunda línea.';
const juridicas = [1,2].map(n => ({revision_id:n, convenio_id:40+n, codigo_convenio:n===1?null:'USB-ORI-2026-00007', solicitud_consecutivo:n===1?'SOL-00000041':null,objeto,tipo_convenio:{id:1,nombre:'Marco de cooperación académica'},responsable:persona,fecha_recepcion:'2026-11-16T15:00:00Z',instancia_juridica:n,numero_ronda:3,version_numero:5}));
const contraparte = juridicas.map(x=>({...x, version_numero:5,enviada_por:persona,fecha_envio:x.fecha_recepcion}));
const convenio = {id:41,codigo:null,objeto,estado:'VIGENTE',fecha_inicio:'2026-01-01',fecha_vencimiento:'2028-01-01',fecha_formalizacion:'2026-06-15',tipo_convenio:{id:1,nombre:'Marco'},contraparte:{nombre:'Universidad de cooperación internacional',tipo:'UNIVERSIDAD',identificacion:'900123456-7',es_aliado_formal:true},etapa:{codigo:'FORMALIZADO',nombre:'Formalizado'},puede_ver_detalle:true};
const aliado = {id:1,nombre:'Universidad aliada de cooperación e investigación internacional',tipo:'UNIVERSIDAD',tipo_identificacion:'NIT',identificacion:'900000017',ciudad:'Cali',correo:persona.correo,telefono:'+57 602 1234567',activo:true,convenios:[convenio]};
const sesion = {id:1,correo:'qa@example.com',nombre_completo:'QA visual',activo:true,tipo_usuario:'INTERNO',rol:{codigo:'ADMINISTRADOR_ORI',nombre:'Administrador ORI'},permisos:['convenios.revisar','convenios.ver','convenios.revisar_contraparte_propia','aliados.ver','usuarios.ver','solicitudes.ver_recibidas','solicitudes.ver_propias']};
const sizes = [[1440,900],[1280,800],[768,1024],[390,844],[360,740],[320,740]];
const pages = [['juridicas','/revisiones-juridicas'],['contraparte','/revisiones-contraparte'],['consulta','/convenios'],['aliado','/aliados/1']];
if(phase==='despues')pages.push(['usuarios','/admin/usuarios'],['aliados','/aliados'],['recibidas','/ori/solicitudes'],['mias','/solicitudes'],['detalle','/convenios/41'],['comparacion','/solicitudes/1/historial']);
sesion.permisos.push('convenios.gestionar_soportes');
const solicitud={id:1,consecutivo:'SOL-00000041',solicitante_nombre:persona.nombre_completo,solicitante_correo:persona.correo,nombre_aliado_propuesto:aliado.nombre,tipo_convenio_nombre:'Marco de cooperación académica',tipo_convenio_id:1,estado:'RADICADA',convenio_id:null,convenio_estado:null,convenio_etapa:null,fecha_radicacion:'2026-11-16T15:00:00Z'};
(async()=>{
 fs.mkdirSync(root,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.ORI_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const u=new URL(route.request().url());let data=[];
  if(u.pathname==='/api/auth/me')data=sesion;
  else if(u.pathname.endsWith('/revisiones-juridicas/pendientes'))data=juridicas;
  else if(u.pathname.endsWith('/revisiones-contraparte/pendientes'))data=contraparte;
  else if(u.pathname==='/api/aliados/1')data=aliado;
  else if(u.pathname==='/api/convenios/catalogos/consulta')data={estados:['VIGENTE'],tipos_contraparte:['UNIVERSIDAD'],programas:[]};
  else if(u.pathname==='/api/convenios')data={items:[convenio],total:1};
  else if(u.pathname==='/api/usuarios')data=[{...sesion,...persona}];
  else if(u.pathname==='/api/aliados')data={items:[aliado],total:1};
  else if(u.pathname==='/api/solicitudes/recibidas'||u.pathname==='/api/solicitudes/mias')data={items:[solicitud],total:1};
  else if(u.pathname==='/api/solicitudes/catalogos')data={solicitante:{tipo_usuario:'INTERNO'},tipos_convenio:[{id:1,nombre:'Marco de cooperación académica'}],tipos_documento:[]};
  else if(u.pathname==='/api/solicitudes/1/historial')data={solicitud_id:1,consecutivo:solicitud.consecutivo,estado:'RADICADA',versiones:[{numero:1,radicada_en:solicitud.fecha_radicacion,devolucion:null},{numero:2,radicada_en:solicitud.fecha_radicacion,devolucion:null}]};
  else if(u.pathname==='/api/solicitudes/1/versiones/2/comparacion')data={solicitud_id:1,hay_cambios:true,version_base:{numero:1},version_comparada:{numero:2},campos:[{campo:'objeto',etiqueta:'Objeto',valor_anterior:objeto,valor_nuevo:objeto+' Ampliación del convenio.'}],documentos:{agregados:[],eliminados:[],sustituidos:[]}};
  else if(u.pathname==='/api/convenios/41')data={...convenio,origen:'MANUAL_ORI',creado_por:persona,creado_en:'2026-01-01T15:00:00Z',porcentaje_avance:100,etapa_actual:convenio.etapa};
  else if(u.pathname==='/api/convenios/41/revisiones')data={revisiones:[],cambios_etapa:[]};
  else if(u.pathname==='/api/convenios/41/revision'||u.pathname==='/api/convenios/41/elaboracion')return route.fulfill({status:404,json:{detail:'Sin revisión pendiente en este convenio de QA'}});
  else if(u.pathname==='/api/convenios/41/documentos')data=[{id:1,nombre_original:'Documento de soporte de cooperación '+ 'nombreExtenso'.repeat(8)+'.pdf',tamano_bytes:20000,fecha_creacion:solicitud.fecha_radicacion,usuario_nombre:persona.nombre_completo}];
  else if(u.pathname==='/api/convenios/41/actividades-utilizacion')data=[{id:1,fecha_ejecucion:'2026-11-16',titulo:'Actividad de cooperación institucional',descripcion:objeto,observaciones:objeto,responsable_nombre:persona.nombre_completo}];
  else if(u.pathname==='/api/convenios/41/evaluacion')return route.fulfill({status:404,json:{detail:'Sin evaluación de QA'}});
  await route.fulfill({json:data});
 });
 const results=[];
 for(const [name,url] of pages.filter(([name])=>!process.env.ORI_QA_FILTER||process.env.ORI_QA_FILTER.split(',').includes(name))) for(const [width,height] of sizes){
  await page.setViewportSize({width,height});await page.goto(baseURL+url);await page.locator('tbody tr').first().waitFor().catch(async e=>{console.log(JSON.stringify({name,width,errors,body:await page.locator('body').innerText()}));throw e});await page.evaluate(()=>document.fonts.ready);
  const measurements=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth,layout:document.querySelector('main.page').className,tables:[...document.querySelectorAll('table')].map(t=>({columns:t.querySelectorAll('thead th').length,width:t.getBoundingClientRect().width,containerWidth:t.parentElement.clientWidth,scrollWidth:t.parentElement.scrollWidth,overflow:getComputedStyle(t.parentElement).overflowX,focusable:t.parentElement.tabIndex}))}));
  results.push({name,width,height,...measurements});
  if((name==='juridicas'&&(width===1440||width===390))||(name==='contraparte'&&width===1440)||(name==='aliado'&&width===390))await page.screenshot({path:`${root}/${phase}-${name}-${width}.png`,fullPage:true});
  if(phase==='despues'){
   if(measurements.page>width+1)throw Error(`Page overflow ${name} ${width}: ${measurements.page}`);
   for(const table of await page.locator('table').all()){
    const region=table.locator('..');await region.focus();
    const needsScroll=await region.evaluate(e=>e.scrollWidth>e.clientWidth+1);
    if(needsScroll){await region.evaluate(e=>e.scrollLeft=0);await page.keyboard.press('ArrowRight');await page.waitForFunction(e=>e.scrollLeft>0,await region.elementHandle());}
    await region.evaluate(e=>e.scrollLeft=e.scrollWidth);
    const last=table.locator('tbody tr').first().locator('td, th').last();
    const a=await last.boundingBox(),b=await region.boundingBox();
    if(a.x+a.width>b.x+b.width+2)throw Error(`Last column inaccessible: ${name} ${width}`);
   }
   if(name==='juridicas'&&(width===390||width===1440))await page.screenshot({path:`${root}/despues-juridicas-${width}-acciones.png`,fullPage:true});
  }
 }
 if(phase==='despues'){
  await page.goto(baseURL+'/revisiones-juridicas?buscar=provisional&tipo=Marco+de+cooperaci%C3%B3n+acad%C3%A9mica&responsable=7');
  await page.getByRole('link',{name:'Revisar',exact:true}).click();
  await page.getByRole('link',{name:'Volver a revisiones jurídicas',exact:true}).click();
  const u=new URL(page.url());if(u.searchParams.get('buscar')!=='provisional'||u.searchParams.get('responsable')!=='7'||!u.searchParams.get('tipo').startsWith('Marco'))throw Error('Context lost');
 }
 fs.writeFileSync(`${root}/${phase}-medidas.json`,JSON.stringify({browser:await browser.version(),syntheticData:true,results,errors},null,2));
 console.log(JSON.stringify({phase,checks:results.length,errors,overflows:results.filter(x=>x.page>x.width+1).map(x=>[x.name,x.width,x.page])}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
