/* ============================================================
   SmartTech S.A.C. — chat.js
   Ruta: D:\smartech\static\js\chat.js
   Conectado al backend Flask (/api/chat) con flujo de 5 pasos:
   1) Perfil  2) Formato  3) Presupuesto  4) Propuesta  5) Periféricos
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Elementos DOM ── */
  const fab        = document.getElementById('chat-fab');
  const chatWindow = document.getElementById('chat-window');
  const messagesEl = document.getElementById('chat-messages');
  const inputEl    = document.getElementById('chat-input');
  const sendBtn    = document.getElementById('chat-send');

  /* ── Estado local del flujo (solo para mostrar los "chips" correctos;
        el estado real de paso/perfil/presupuesto vive en la sesión Flask) ── */
  let localStep = 0; // 0=sin iniciar, 1..5 según respuesta del backend

  /* ── Chips sugeridos por paso (ayudan a no escribir todo a mano) ── */
  const CHIPS_PASO_1 = ['🎮 Gamer', '📐 Ingeniería o Diseño', '🎒 Estudiante de Colegio', '💼 Uso Doméstico / Ofimática'];
  const CHIPS_PASO_2 = ['CPU de fábrica', 'CPU para armar', 'Laptop', 'CPU All-in-One'];
  const CHIPS_PASO_5 = ['👍 Acepto, ver periféricos', 'Quiero modificar algo'];

  /* ── Toggle ventana del chat ── */
  fab.addEventListener('click', () => {
    chatWindow.classList.toggle('open');
    if (chatWindow.classList.contains('open') && messagesEl.children.length === 0) {
      startConversation();
    }
  });

  /* ── Inicio: el primer mensaje vacío dispara el saludo + Paso 1 desde el backend ── */
  function startConversation() {
    sendToBackend('hola');
  }

  /* ── Enviar mensaje (tecla Enter o botón) ── */
  sendBtn.addEventListener('click', sendUserText);
  inputEl.addEventListener('keydown', e => { if (e.key === 'Enter') sendUserText(); });

  function sendUserText() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    appendUser(text);
    sendToBackend(text);
  }

  /* ── Click en un chip: se muestra como mensaje del usuario y se envía igual que texto libre ── */
  function handleChipClick(value) {
    appendUser(value);
    sendToBackend(value);
  }

  /* ── Llamada real al backend Flask (/api/chat) ── */
  async function sendToBackend(mensaje) {
    showTyping();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensaje })
      });

      if (!res.ok) throw new Error('Error de red');
      const data = await res.json();
      hideTyping();
      renderBackendResponse(data.respuesta || 'No obtuve respuesta del servidor.');

    } catch (err) {
      hideTyping();
      appendBot('⚠️ No pude conectarme con el asistente en este momento. Por favor intenta nuevamente en unos segundos.');
    }
  }

  /* ── Decide qué chips mostrar según el contenido de la respuesta del bot ── */
  function renderBackendResponse(htmlRespuesta) {
    let chips = [];
    const texto = htmlRespuesta.toLowerCase();

    // CORRECCIÓN: Ajuste de textos clave para que coincidan con routes.py
    if (texto.includes('perfil de uso') || texto.includes('cuál es tu perfil')) {
      chips = CHIPS_PASO_1;
      localStep = 1;
    } else if (texto.includes('formato de computadora') || texto.includes('qué tipo de formato') || texto.includes('formato prefieres')) {
      chips = CHIPS_PASO_2;
      localStep = 2;
    } else if (texto.includes('presupuesto máximo estimado') || texto.includes('presupuesto máximo')) {
      chips = [];
      localStep = 3;
    } else if (texto.includes('te convence esta configuración') || texto.includes('te convence?')) {
      chips = CHIPS_PASO_5;
      localStep = 4;
    } else if (texto.includes('fase final') || texto.includes('periféricos recomendados')) {
      chips = [];
      localStep = 5;
    }

    appendBot(htmlRespuesta, chips, true);
  }

  /* ── Indicador "escribiendo…" ── */
  function showTyping() {
    const typing = document.createElement('div');
    typing.className = 'msg msg--bot';
    typing.id = 'typing-indicator';
    typing.innerHTML = `
      <div class="msg__avatar">🤖</div>
      <div class="msg__bubble msg__bubble--typing">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>`;
    messagesEl.appendChild(typing);
    scrollDown();
  }

  function hideTyping() {
    const typing = document.getElementById('typing-indicator');
    if (typing) typing.remove();
  }

  /* ── Helpers de renderizado ── */
  function appendBot(content, chips = [], isHtml = false) {
    const msg = document.createElement('div');
    msg.className = 'msg msg--bot';

    const avatar = `<div class="msg__avatar">🤖</div>`;
    const bubbleContent = isHtml ? content : escHtml(content);

    let chipsHtml = '';
    if (chips.length) {
      const chipItems = chips.map(c =>
        `<span class="chip" data-value="${escAttr(c)}">${c}</span>`
      ).join('');
      chipsHtml = `<div class="chat-chips">${chipItems}</div>`;
    }

    msg.innerHTML = `
      ${avatar}
      <div>
        <div class="msg__bubble">${bubbleContent}</div>
        ${chipsHtml}
      </div>`;

    messagesEl.appendChild(msg);
    scrollDown();

    msg.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        // Limpia los chips ya usados para que no se vuelvan a presionar
        msg.querySelector('.chat-chips')?.remove();
        handleChipClick(chip.dataset.value);
      });
    });
  }

  function appendUser(text) {
    const msg = document.createElement('div');
    msg.className = 'msg msg--user';
    msg.innerHTML = `<div class="msg__bubble">${escHtml(text)}</div>`;
    messagesEl.appendChild(msg);
    scrollDown();
  }

  function scrollDown() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function escHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escAttr(str) {
    return escHtml(str).replace(/'/g, '&#39;');
  }

});