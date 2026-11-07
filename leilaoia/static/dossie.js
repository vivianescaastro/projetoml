/* Renderização do dossiê — compartilhada pelo app (index.html) e pelo espelho do histórico. */
(function(g){
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const brl=v=>v==null?'—':'R$ '+Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const PAL=['#4c8dff','#f08a24','#2fbf71','#c99bf0','#e6a817','#e5534b','#5fd0d0','#d26ea8','#8b93a5'];
g.dossieHtml=function(d,opts){
  opts=opts||{};
  const v=d.veredito,c=d.custos,f=d.ficha;
  const segs=[{n:'Lance',v:c.lance}].concat(c.itens.filter(i=>i.computa_no_total&&i.valor_calculado!=null).map(i=>({n:i.nome,v:i.valor_calculado})));
  const tot=segs.reduce((a,s)=>a+s.v,0)||1;
  const li=l=>l.length?'<ul>'+l.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'';
  return `<h2>Dossiê de decisão ${d.id?`<span class="idtag">${esc(d.id)}</span>`:'<span class="mut">(não salvo no histórico)</span>'}</h2>
  <div class="mut" style="margin:-6px 0 10px">${esc(d.gerado_em)} · ${esc(d.arquivo)}</div>
  <div class="verd ${v.cor}"><b class="big">${esc(v.decisao)}</b><div style="flex:1;min-width:240px">
   ${v.bloqueios.length?'<div class="bad"><b>Bloqueios</b>'+li(v.bloqueios)+'</div>':''}
   ${v.atencoes.length?'<div class="warn"><b>Atenção</b>'+li(v.atencoes)+'</div>':''}
   ${v.positivos.length?'<div class="ok"><b>A favor</b>'+li(v.positivos)+'</div>':''}</div>
   ${opts.pdf?'<button id="btnPdf">⬇ Baixar dossiê em PDF</button>':''}</div>
  ${(d.respostas||[]).length?`<h2 style="margin-top:18px">Objetivo da compra — perguntas e respostas</h2><div class="tbl"><table>${d.respostas.map(r=>`<tr><td>${esc(r.pergunta)}</td><td><b>${esc(r.resposta)}</b></td></tr>`).join('')}</table></div>`:''}
  <div class="kpis">
   <div class="kpi"><small>Lance simulado</small><b>${brl(c.lance)}</b></div>
   <div class="kpi"><small>Custo total</small><b>${brl(c.custo_total)}</b><small>+${c.acrescimo_pct}% sobre o lance</small></div>
   <div class="kpi"><small>Só o que está no edital</small><b>${brl(c.subtotal_edital)}</b><small>+ estimativas ${brl(c.extras_estimados)} · seus ${brl(c.extras_usuario)}</small></div>
   <div class="kpi"><small>Valor de revenda/mercado</small><b>${brl(c.valor_venda_ref)}</b></div>
   <div class="kpi"><small>Lucro · margem</small><b class="${c.margem_pct<0?'bad':''}">${c.lucro!=null?brl(c.lucro)+' · '+c.margem_pct+'%':'—'}</b></div>
   <div class="kpi"><small>Lance máximo recomendado</small><b>${brl(c.lance_maximo_recomendado)}</b></div></div>
  ${d.aviso_modo?`<div class="warn">⚠ ${esc(d.aviso_modo)}</div>`:''}
  <h2 style="margin-top:18px">Composição do custo</h2>
  <div class="stack">${segs.map((s,i)=>`<div title="${esc(s.n)} ${brl(s.v)}" style="width:${s.v/tot*100}%;background:${PAL[i%PAL.length]}"></div>`).join('')}</div>
  <div class="leg">${segs.map((s,i)=>`<span><i style="background:${PAL[i%PAL.length]}"></i>${esc(s.n)} ${brl(s.v)}</span>`).join('')}</div>
  <div class="cols" style="margin-top:16px"><div><h2>Custos detalhados</h2><div class="tbl"><table>
   <tr><th>Item</th><th>Valor</th><th>Pago a · quando · como</th></tr>
   <tr><td>Lance arrematado</td><td>${brl(c.lance)}</td><td class="mut">vendedor / leiloeiro</td></tr>
   ${c.itens.map(i=>`<tr><td>${esc(i.nome)}<div class="mut">${i.tipo==='pct_lance'&&i.valor!=null?i.valor+'% do lance':i.tipo==='diaria'?brl(i.valor)+' × '+i.quantidade+' dias':''} ${i.origem!=='edital'?'<span class="badge" style="background:#3a2a14;color:#f0b062">'+esc(i.origem)+'</span>':''}${i.obs?'<br>'+esc(i.obs):''}${i.fonte&&i.origem==='edital'?'<div class="quote">“'+esc(i.fonte)+'”'+(i.pagina?' <b>(p. '+i.pagina+')</b>':'')+'</div>':''}</div></td>
    <td>${i.valor_calculado!=null?brl(i.valor_calculado):'<span class="warn">a confirmar</span>'}${i.computa_no_total?'':'<div class="mut">abatido do preço</div>'}</td>
    <td class="mut">${esc([i.pago_a,i.quando,i.como].filter(Boolean).join(' · ')||'—')}</td></tr>`).join('')}
   <tr><td><b>Total</b></td><td><b>${brl(c.custo_total)}</b></td><td></td></tr></table></div>
   <p class="mut"><b>Como pagar:</b> ${esc(f.forma_pagamento||'—')} · <b>prazo:</b> ${esc(f.prazo_pagamento_texto||'—')}${f.parcelamento?'<br><b>Parcelamento:</b> '+esc(f.parcelamento):''}</p>
   <h2>A quem pagar</h2><div class="tbl"><table>${c.por_beneficiario.map(b=>`<tr><td>${esc(b.pago_a)}</td><td>${brl(b.valor)}</td></tr>`).join('')}</table></div></div>
  <div><h2>Prazos</h2><div class="tl">${d.prazos.map(p=>`<div class="${p.alerta?'al':''}"><b>${esc(p.data)}</b> — ${esc(p.evento)}${p.alerta?'<br><span class="warn">⚠ '+esc(p.alerta)+'</span>':''}</div>`).join('')||'<span class="mut">Nenhum prazo identificado.</span>'}</div>
   <h2 style="margin-top:18px">Ficha do edital</h2><div class="mut">Tipo: ${esc(d.tipo_leilao)} · leiloeiro: ${esc(f.leiloeiro||'—')} ${f.leiloeiro_credenciado?'(credenciado)':''}<br>Processo: ${esc(f.processo||'—')} ${esc(f.juizo||'')}<br>Avaliação ${brl(f.valor_avaliacao)} · 1ª praça ${brl(f.lance_minimo_1)} · 2ª praça ${brl(f.lance_minimo_2)}<br>Comissão: ${f.comissao_pct!=null?f.comissao_pct+'%':'—'} · débitos: ${esc(f.debitos_responsabilidade||'—')}<br>${f.ocupacao?'Ocupação: '+esc(f.ocupacao):''}</div></div></div>
  <h2 style="margin-top:18px">Valores citados no edital (texto literal)</h2>
  <p class="mut">Toda passagem do PDF que cita R$ ou %, na ordem do edital — inclusive o que o app não soube classificar como custo.</p>
  <div class="tbl"><table><tr><th>Pág.</th><th>Valores</th><th>Trecho do edital</th></tr>${(f.valores_encontrados||[]).map(t=>`<tr><td>${t.pagina||'—'}</td><td>${esc(t.valores.join(' · '))}</td><td class="mut">${esc(t.trecho)}</td></tr>`).join('')||'<tr><td colspan=3 class="mut">Nenhum valor encontrado.</td></tr>'}</table></div>
  <h2 style="margin-top:18px">Pontos de atenção — leilão ${esc(d.tipo_leilao)}</h2>
  ${d.pontos.map(p=>`<div class="pt ${p.severidade}"><b>${esc(p.titulo)}</b> — ${esc(p.descricao)}${p.fundamento?`<small>Fundamento: ${esc(p.fundamento)}</small>`:''}${p.trecho&&p.severidade!=='ok'?`<small>“${esc(p.trecho.slice(0,260))}”</small>`:''}</div>`).join('')}`;
};
})(window);
