/* CARS Auto Center · conteúdo do pré-diagnóstico 3D e das luzes do painel.
   n = urgência: 1 pode agendar · 2 traga nesta semana · 3 pare e chame a oficina.
   view = câmera do three.js (Y para cima, frente do carro em +X, lado direito em +Z). */
window.CARS_DATA = {
  whatsapp: '5512996703686',
  zones: [
    {
      id: 'motor', name: 'Motor', anchor: 'motor_tampa', xray: true,
      view: { pos: [3.7, 2.5, 2.3], target: [1.35, 0.62, 0] },
      what: 'Transforma a queima do combustível em movimento: ar e combustível entram, a vela solta a faísca e os pistões giram o virabrequim.',
      symptoms: [
        { t: 'Luz da injeção acesa', c: 'Falha de ignição, sensor ou injeção eletrônica', n: 2 },
        { t: 'Motor falhando ou tremendo parado', c: 'Velas, bobinas ou bicos injetores', n: 2 },
        { t: 'Perda de força nas subidas', c: 'Filtros entupidos, injeção ou compressão baixa', n: 2 },
        { t: 'Fumaça azulada no escape', c: 'Motor queimando óleo (anéis ou retentores de válvula)', n: 2 },
        { t: 'Mancha de óleo no chão da garagem', c: 'Vazamento em juntas ou retentores', n: 2 },
        { t: 'Luz do óleo acesa', c: 'Pressão de óleo baixa: desligue o motor', n: 3 }
      ]
    },
    {
      id: 'correia', name: 'Correia dentada', anchor: 'correia_dentada', xray: true,
      view: { pos: [2.9, 1.5, -2.7], target: [1.4, 0.6, -0.3] },
      what: 'Sincroniza o virabrequim com o comando de válvulas. Se ela rompe com o motor girando, pistão e válvula se chocam.',
      symptoms: [
        { t: 'Chiado agudo ao ligar o carro', c: 'Correia de acessórios ressecada ou frouxa', n: 1 },
        { t: 'Passou da quilometragem de troca', c: 'Troca preventiva vencida: se romper, pode empenar válvulas', n: 3 },
        { t: 'Estalo ou batida na frente do motor', c: 'Tensor ou polia com folga', n: 2 },
        { t: 'Motor de partida gira, mas o carro não pega', c: 'Possível correia rompida: não insista na partida', n: 3 }
      ]
    },
    {
      id: 'cambio', name: 'Câmbio e embreagem', anchor: 'cambio_caixa', xray: true,
      view: { pos: [3.0, 1.3, 2.9], target: [1.35, 0.45, 0.3] },
      what: 'A embreagem liga e desliga o motor das rodas; o câmbio escolhe a relação certa para cada velocidade.',
      symptoms: [
        { t: 'Embreagem patinando (acelera e não sobe)', c: 'Disco de embreagem gasto', n: 2 },
        { t: 'Pedal da embreagem duro ou alto', c: 'Platô, atuador ou cabo da embreagem', n: 2 },
        { t: 'Marchas arranhando ao engatar', c: 'Sincronizados ou regulagem do trambulador', n: 2 },
        { t: 'Trancos no câmbio automático', c: 'Fluido do câmbio vencido ou contaminado', n: 2 },
        { t: 'Estalo ao fazer curva fechada', c: 'Junta homocinética gasta', n: 2 }
      ]
    },
    {
      id: 'bateria', name: 'Bateria e elétrica', anchor: 'bateria_caixa', xray: true,
      view: { pos: [2.8, 2.6, -2.3], target: [1.15, 0.72, -0.45] },
      what: 'A bateria dá a partida. Com o motor ligado, o alternador recarrega a bateria e alimenta o carro, por volta de 14 volts.',
      symptoms: [
        { t: 'Partida fraca ou carro não liga de manhã', c: 'Bateria no fim da vida ou terminais oxidados', n: 2 },
        { t: 'Luz da bateria acesa no painel', c: 'Alternador não está carregando', n: 3 },
        { t: 'Luzes oscilando ou fracas', c: 'Alternador, regulador de tensão ou mau contato', n: 2 },
        { t: 'Bateria arria com o carro parado', c: 'Consumo de corrente com o carro desligado (fuga)', n: 2 },
        { t: 'Vidro, trava ou som falhando', c: 'Fusível, relé ou chicote', n: 1 }
      ]
    },
    {
      id: 'arrefecimento', name: 'Arrefecimento', anchor: 'arrefecimento_radiador', xray: true,
      view: { pos: [4.6, 1.7, 1.3], target: [1.75, 0.52, 0] },
      what: 'O líquido passa pelo motor, leva o calor até o radiador e volta resfriado. O motor trabalha perto de 90 °C.',
      symptoms: [
        { t: 'Ponteiro da temperatura subindo', c: 'Falta de líquido, válvula termostática ou ventoinha', n: 3 },
        { t: 'Precisa completar água toda semana', c: 'Vazamento em mangueira, radiador ou bomba d’água', n: 2 },
        { t: 'Ventoinha não liga ou não desliga', c: 'Sensor de temperatura, relé ou motor da ventoinha', n: 2 },
        { t: 'Cheiro doce ou vapor saindo do capô', c: 'Vazamento de líquido de arrefecimento', n: 3 }
      ]
    },
    {
      id: 'freios', name: 'Freios', anchor: 'freio_pinca_DD', xray: false,
      view: { pos: [2.7, 0.95, 3.1], target: [1.3, 0.36, 0.72] },
      what: 'O pedal pressiona o fluido, que empurra as pastilhas contra o disco. O atrito transforma o movimento em calor.',
      symptoms: [
        { t: 'Chiado ou rangido ao frear', c: 'Pastilhas no fim: o aviso de desgaste raspa no disco', n: 2 },
        { t: 'Pedal baixo, mole ou afundando', c: 'Ar no sistema ou vazamento de fluido', n: 3 },
        { t: 'Volante treme ao frear', c: 'Disco de freio empenado', n: 2 },
        { t: 'Carro puxa para um lado ao frear', c: 'Pinça travando ou desgaste desigual', n: 3 },
        { t: 'Luz do freio acesa no painel', c: 'Fluido baixo ou falha no sistema', n: 3 }
      ]
    },
    {
      id: 'suspensao', name: 'Suspensão e direção', anchor: 'susp_mola_DD', xray: true,
      view: { pos: [2.3, 1.3, 3.4], target: [1.3, 0.6, 0.5] },
      what: 'As molas seguram o peso e os amortecedores controlam o balanço. Juntos, mantêm o pneu colado no chão.',
      symptoms: [
        { t: 'Barulho seco em buracos e lombadas', c: 'Buchas, bieletas ou batentes gastos', n: 2 },
        { t: 'Carro balança e demora a firmar', c: 'Amortecedores no fim', n: 2 },
        { t: 'Carro mais baixo de um lado', c: 'Mola quebrada ou cansada', n: 2 },
        { t: 'Volante com folga ou batendo', c: 'Terminal ou caixa de direção', n: 3 }
      ]
    },
    {
      id: 'pneus', name: 'Pneus e geometria', anchor: 'pneu_TD', xray: false,
      view: { pos: [0.3, 1.05, 4.7], target: [0, 0.38, 0.6] },
      what: 'São a única parte do carro que toca o chão. Pressão, alinhamento e balanceamento decidem a aderência e o desgaste.',
      symptoms: [
        { t: 'Carro puxando para um lado na reta', c: 'Alinhamento fora ou pressão desigual', n: 1 },
        { t: 'Volante torto com o carro reto', c: 'Alinhamento (geometria)', n: 1 },
        { t: 'Volante vibra acima de 80 km/h', c: 'Balanceamento das rodas', n: 1 },
        { t: 'Pneu gasto só na borda', c: 'Cambagem fora ou pressão errada', n: 2 },
        { t: 'Bolha na lateral do pneu', c: 'Estrutura do pneu rompida: troque antes de rodar', n: 3 }
      ]
    },
    {
      id: 'escape', name: 'Escapamento', anchor: 'escape_ponteira', xray: true,
      view: { pos: [-4.4, 0.7, 2.5], target: [-1.4, 0.32, 0.3] },
      what: 'Leva os gases do motor para fora, passando pelo catalisador, que reduz os poluentes, e pelo silencioso.',
      symptoms: [
        { t: 'Ronco alto, como de moto', c: 'Escapamento furado ou silencioso solto', n: 1 },
        { t: 'Fumaça preta', c: 'Mistura rica: injeção ou sonda lambda', n: 2 },
        { t: 'Fumaça branca grossa e constante', c: 'Pode ser junta do cabeçote: líquido entrando no motor', n: 3 },
        { t: 'Cheiro de combustível ou de ovo podre', c: 'Catalisador ou mistura desregulada', n: 2 }
      ]
    },
    {
      id: 'iluminacao', name: 'Faróis e lanternas', anchor: 'luz_farol_d', xray: false,
      view: { pos: [5.0, 1.35, 1.1], target: [1.9, 0.68, 0] },
      what: 'Faróis, lanternas, setas e luz de freio: é como o carro vê e é visto, de dia e de noite.',
      symptoms: [
        { t: 'Farol queimado ou fraco', c: 'Lâmpada, fusível ou conector oxidado', n: 1 },
        { t: 'Seta piscando rápido', c: 'Lâmpada de seta queimada', n: 1 },
        { t: 'Luz de freio não acende', c: 'Lâmpada ou interruptor do pedal', n: 2 },
        { t: 'Farol amarelado e opaco', c: 'Lente oxidada, que reduz o alcance à noite', n: 1 }
      ]
    }
  ],

  /* Luzes do painel. level 3 = vermelha (pare), 2 = amarela (agende logo). */
  lights: [
    { id: 'oleo', name: 'Pressão do óleo', level: 3,
      svg: '<path d="M2.5 10.5h4l2-2.5h6l6.5 3-4 5.5H8.5l-1.5-3.5h-4.5z"/><path d="M8.5 8V6h4"/><path d="M21.5 16.5c0 .9-.6 1.6-1.3 1.6s-1.2-.7-1.2-1.6c0-.9 1.2-2.4 1.2-2.4s1.3 1.5 1.3 2.4z"/>',
      text: 'O motor está sem pressão de óleo: falta óleo ou a bomba falhou. Rodar assim pode fundir o motor em poucos minutos.',
      todo: 'Pare em local seguro, desligue o motor e não ligue de novo. Chame a oficina.' },
    { id: 'temperatura', name: 'Temperatura do motor', level: 3,
      svg: '<path d="M10.5 3.5h3v10a3.2 3.2 0 1 1-3 0z"/><path d="M13.5 6.5h3M13.5 9.5h3"/><path d="M2.5 20c2 0 2-1.2 4-1.2s2 1.2 4 1.2 2-1.2 4-1.2 2 1.2 4 1.2 2-1.2 3-1.2"/>',
      text: 'O motor passou da temperatura de trabalho. Pode ser falta de líquido, ventoinha parada ou válvula termostática travada.',
      todo: 'Pare, desligue e espere esfriar. Nunca abra o reservatório com o motor quente.' },
    { id: 'bateria', name: 'Carga da bateria', level: 3,
      svg: '<rect x="2.5" y="7" width="19" height="12" rx="1.5"/><path d="M6 7V5h3v2M15 7V5h3v2"/><path d="M5.5 13h4M14.5 13h4M16.5 11v4"/>',
      text: 'O alternador não está carregando. O carro roda só com o que sobrou na bateria e pode apagar no meio do caminho.',
      todo: 'Desligue ar e som e venha direto para a oficina, sem desligar o motor no trajeto.' },
    { id: 'freio', name: 'Sistema de freio', level: 3,
      svg: '<circle cx="12" cy="12" r="6"/><path d="M5 5.5a9.5 9.5 0 0 0 0 13M19 5.5a9.5 9.5 0 0 1 0 13"/><path d="M12 8.5v4.2M12 15.2v.3"/>',
      text: 'Freio de mão puxado, fluido abaixo do mínimo ou falha no sistema hidráulico.',
      todo: 'Confira o freio de mão. Se continuar acesa, não rode: o pedal pode afundar.' },
    { id: 'airbag', name: 'Airbag', level: 3,
      svg: '<circle cx="7.5" cy="5" r="2"/><path d="M6.5 9 5.5 15h5l2.5 5"/><path d="M5.5 15 4 20"/><circle cx="16.5" cy="11.5" r="4"/>',
      text: 'O sistema do airbag encontrou uma falha e a bolsa pode não abrir numa batida.',
      todo: 'O carro anda normalmente, mas agende a verificação o quanto antes.' },
    { id: 'injecao', name: 'Injeção eletrônica', level: 2,
      svg: '<path d="M3 10.5h2V8.5h3V6.5h6v2h2.5l2 2H21v6h-2.5l-2 2H8l-2-2H3z"/><path d="M1.5 10v6M8 6.5h6"/>',
      text: 'A central do motor encontrou uma falha em sensor, ignição ou mistura. Se estiver piscando, a falha é séria e pode danificar o catalisador.',
      todo: 'Acesa fixa: agende a leitura com scanner. Piscando: reduza a velocidade e venha logo.' },
    { id: 'abs', name: 'ABS', level: 2,
      svg: '<circle cx="12" cy="12" r="7"/><path d="M3.5 5.5a10 10 0 0 0 0 13M20.5 5.5a10 10 0 0 1 0 13"/><text x="12" y="14.6" text-anchor="middle" font-size="6.4" font-weight="800" font-family="Archivo, Arial, sans-serif" stroke="none" fill="currentColor">ABS</text>',
      text: 'O antitravamento está desligado. O freio comum funciona, mas as rodas podem travar numa freada forte.',
      todo: 'Rode com mais distância do carro da frente e agende a verificação dos sensores.' },
    { id: 'pneu', name: 'Pressão dos pneus', level: 2,
      svg: '<path d="M5.5 7c-1.4 2.6-1.4 7.4 0 10M18.5 7c1.4 2.6 1.4 7.4 0 10"/><path d="M5.5 7c3-1 10-1 13 0M5.5 17c3 1 10 1 13 0"/><path d="M4.5 19.5h2M9 20h2M13 20h2M17.5 19.5h2"/><path d="M12 9v4M12 15v.3"/>',
      text: 'Um ou mais pneus estão com a pressão abaixo da recomendada.',
      todo: 'Calibre na próxima parada. Se voltar a acender, pode ser um furo lento.' },
    { id: 'direcao', name: 'Direção elétrica', level: 2,
      svg: '<circle cx="11" cy="12" r="8"/><circle cx="11" cy="12" r="2.2"/><path d="M3.5 11h5.4M13.1 11h5.4M11 14.2V20"/><path d="M21.5 7v5M21.5 14.5v.3"/>',
      text: 'A assistência da direção falhou ou foi limitada. O volante fica pesado, principalmente em manobra.',
      todo: 'Dirija com cuidado e traga para a análise elétrica.' },
    { id: 'tracao', name: 'Controle de estabilidade', level: 2,
      svg: '<path d="M4.5 12.5 6.8 8h10.4l2.3 4.5V16h-15z"/><circle cx="7.5" cy="16" r="1.4"/><circle cx="16.5" cy="16" r="1.4"/><path d="M6.5 22c1.2-1.2 1.2-2 0-3M12 22.5c1.2-1.2 1.2-2 0-3M17.5 22c1.2-1.2 1.2-2 0-3"/>',
      text: 'Piscando: o sistema está agindo em pista escorregadia. Acesa fixa: ele está desligado ou com falha.',
      todo: 'Se ficar acesa fixa, agende a verificação.' },
    { id: 'combustivel', name: 'Reserva de combustível', level: 2,
      svg: '<path d="M4.5 20V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v15M3 20h12"/><path d="M4.5 10h9"/><path d="M13.5 8h2l2 2.5v6.5a1.5 1.5 0 0 0 3 0V8.5l-2.5-2.5"/>',
      text: 'Restam poucos litros no tanque. Rodar sempre na reserva puxa sujeira do fundo e força a bomba de combustível.',
      todo: 'Abasteça assim que possível.' },
    { id: 'pastilha', name: 'Desgaste das pastilhas', level: 2,
      svg: '<circle cx="12" cy="12" r="5"/><path d="M5 5.5a9.5 9.5 0 0 0 0 13M19 5.5a9.5 9.5 0 0 1 0 13" stroke-dasharray="2.2 2"/><path d="M8 4.5a10.5 10.5 0 0 0 0 15M16 4.5a10.5 10.5 0 0 1 0 15" opacity="0"/>',
      text: 'O sensor de desgaste avisou que as pastilhas chegaram ao fim.',
      todo: 'Agende a troca nesta semana para não riscar o disco.' }
  ]
};
