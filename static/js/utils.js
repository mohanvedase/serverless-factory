/**
 * Serverless Automation Factory — Global JS utilities
 */

// ── Toast notifications ──────────────────────────────────────────────────────
window.showToast = function(msg, type = 'info') {
  const colors = { success:'#10b981', error:'#ef4444', info:'#06b6d4', warn:'#f59e0b' };
  const icons  = { success:'fa-check-circle', error:'fa-circle-xmark', info:'fa-circle-info', warn:'fa-triangle-exclamation' };
  const toast  = document.createElement('div');
  toast.style.cssText = [
    'position:fixed','bottom:1.5rem','right:1.5rem','z-index:9999',
    'background:var(--sf-surface)','border:1px solid '+colors[type],
    'color:var(--sf-text)','padding:.75rem 1.1rem','border-radius:.65rem',
    'font-size:.84rem','box-shadow:0 6px 24px rgba(0,0,0,.35)',
    'display:flex','align-items:center','gap:.5rem',
    'animation:toastIn .2s ease','max-width:320px',
  ].join(';');
  toast.innerHTML = `<i class="fa-solid ${icons[type]||icons.info}" style="color:${colors[type]}"></i>${msg}`;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'opacity .3s, transform .3s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 320);
  }, 3200);
};

// ── Inject keyframes ─────────────────────────────────────────────────────────
(function(){
  const s = document.createElement('style');
  s.textContent = '@keyframes toastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}';
  document.head.appendChild(s);
})();

// ── Copy ARN to clipboard on click ───────────────────────────────────────────
document.addEventListener('click', function(e) {
  const el = e.target.classList.contains('arn-cell') ? e.target : e.target.closest('.arn-cell');
  if (!el) return;
  const text = el.title || el.textContent.trim();
  if (!text || text === '—') return;
  navigator.clipboard.writeText(text).then(() => {
    const orig = el.textContent;
    el.textContent = '✓ Copied!';
    setTimeout(() => { el.textContent = orig; }, 1200);
    showToast('ARN copied to clipboard', 'success');
  }).catch(() => {});
});
