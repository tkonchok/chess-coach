'use strict';
const statusNode = document.querySelector('[data-poll]');
if (statusNode) {
  async function poll() {
    try {
      const response = await fetch(statusNode.dataset.poll, {signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error('Status unavailable');
      const job = await response.json();
      if (job.status === 'completed' || job.status === 'failed') {
        window.location.reload();
        return;
      }
      statusNode.textContent = {queued:'Queued',running:'Analyzing'}[job.status] || job.status;
    } catch (_) {
      statusNode.textContent = 'Could not check status. Retrying; your analysis remains saved.';
    }
    setTimeout(poll, 2000);
  }
  setTimeout(poll, 1000);
}
