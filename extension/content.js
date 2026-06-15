let overlay = null;
let selection = null;
let actionsBox = null;
let startX = 0, startY = 0;
let rect = null;
let isSelecting = false;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'start_selection') {
    startSelection();
    sendResponse({ ok: true });
  } else if (message.type === 'show_error') {
    alert(message.message);
    sendResponse({ ok: true });
  }
});

function startSelection() {
  cleanup();

  overlay = document.createElement('div');
  overlay.className = 'rfa-overlay';
  overlay.addEventListener('mousedown', onMouseDown);
  overlay.addEventListener('mousemove', onMouseMove);
  overlay.addEventListener('mouseup', onMouseUp);
  document.body.appendChild(overlay);
}

function onMouseDown(e) {
  startX = e.clientX;
  startY = e.clientY;
  isSelecting = true;

  selection = document.createElement('div');
  selection.className = 'rfa-selection';
  document.body.appendChild(selection);
}

function onMouseMove(e) {
  if (!isSelecting || !selection) return;

  const x = Math.min(startX, e.clientX);
  const y = Math.min(startY, e.clientY);
  const w = Math.abs(e.clientX - startX);
  const h = Math.abs(e.clientY - startY);

  selection.style.left = x + 'px';
  selection.style.top = y + 'px';
  selection.style.width = w + 'px';
  selection.style.height = h + 'px';

  rect = { x, y, width: w, height: h };
}

function onMouseUp(e) {
  if (!isSelecting) return;
  isSelecting = false;

  if (!rect || rect.width < 10 || rect.height < 10) {
    showError('选区太小，请重新框选');
    return;
  }

  showActions(rect);
}

function showActions(rect) {
  if (actionsBox) actionsBox.remove();

  actionsBox = document.createElement('div');
  actionsBox.className = 'rfa-actions';
  actionsBox.style.left = (rect.x + rect.width - 160) + 'px';
  actionsBox.style.top = (rect.y + rect.height + 8) + 'px';

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'rfa-btn rfa-btn-confirm';
  confirmBtn.textContent = '确认截图';
  confirmBtn.onclick = () => {
    confirmCapture(rect);
  };

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'rfa-btn rfa-btn-cancel';
  cancelBtn.textContent = '取消';
  cancelBtn.onclick = cleanup;

  actionsBox.appendChild(confirmBtn);
  actionsBox.appendChild(cancelBtn);
  document.body.appendChild(actionsBox);
}

function confirmCapture(rect) {
  const dpr = window.devicePixelRatio || 1;
  const scaledRect = {
    x: Math.round(rect.x * dpr),
    y: Math.round(rect.y * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr),
    pageWidth: Math.round(window.innerWidth * dpr),
    pageHeight: Math.round(window.innerHeight * dpr),
  };

  cleanup();

  chrome.runtime.sendMessage({ type: 'capture_area', rect: scaledRect }, (response) => {
    if (response && response.error) {
      alert(response.error);
    }
  });
}

function showError(msg) {
  cleanup();
  alert('阅读助手: ' + msg);
}

function cleanup() {
  if (overlay) { overlay.remove(); overlay = null; }
  if (selection) { selection.remove(); selection = null; }
  if (actionsBox) { actionsBox.remove(); actionsBox = null; }
}
