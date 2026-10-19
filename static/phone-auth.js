(() => {
  const form = document.getElementById('phone-auth');
  const button = document.getElementById('send-code');
  const message = document.getElementById('sms-message');
  button.addEventListener('click', async () => {
    if (!form.elements.phone.reportValidity()) return;
    button.disabled = true;
    try {
      const response = await fetch(form.dataset.sendUrl, {method: 'POST', body: new FormData(form)});
      const data = await response.json();
      message.textContent = data.message + (data.demo_code ? `，演示验证码：${data.demo_code}` : '');
      if (!response.ok) { button.disabled = false; return; }
      let remaining = data.retry_after;
      button.textContent = `${remaining}秒后重试`;
      const timer = setInterval(() => {
        remaining -= 1;
        button.textContent = remaining > 0 ? `${remaining}秒后重试` : '重新获取验证码';
        if (remaining <= 0) { clearInterval(timer); button.disabled = false; }
      }, 1000);
    } catch (_) {
      message.textContent = '发送失败，请稍后重试';
      button.disabled = false;
    }
  });
})();
