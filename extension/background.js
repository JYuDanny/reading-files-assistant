const BACKEND_URL = 'http://localhost:8000';

chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'capture-screenshot') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
      alert('此页面不支持截图');
      return;
    }

    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'start_selection' });
    } catch {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
      await chrome.scripting.insertCSS({
        target: { tabId: tab.id },
        files: ['content.css']
      });
      await chrome.tabs.sendMessage(tab.id, { type: 'start_selection' });
    }
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'capture_area') {
    handleCaptureArea(message.rect, sender.tab.windowId).then(sendResponse);
    return true;
  }
});

async function handleCaptureArea(rect, windowId) {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
      format: 'png'
    });

    const cropped = await cropImage(dataUrl, rect);

    try {
      const healthResp = await fetch(`${BACKEND_URL}/api/health`);
      if (!healthResp.ok) throw new Error('Backend not available');
    } catch {
      return { error: '阅读助手后端未启动，请先运行 backend/main.py' };
    }

    const resp = await fetch(`${BACKEND_URL}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: cropped })
    });

    if (!resp.ok) {
      const err = await resp.json();
      return { error: err.detail || '创建会话失败' };
    }

    const data = await resp.json();

    chrome.tabs.create({ url: data.chat_url });

    return { success: true };
  } catch (e) {
    return { error: e.message };
  }
}

async function cropImage(dataUrl, rect) {
  const response = await fetch(dataUrl);
  const blob = await response.blob();
  const bitmap = await createImageBitmap(blob, rect.x, rect.y, rect.width, rect.height);

  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(bitmap, 0, 0);

  const croppedBlob = await canvas.convertToBlob({ type: 'image/png' });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(croppedBlob);
  });
}
