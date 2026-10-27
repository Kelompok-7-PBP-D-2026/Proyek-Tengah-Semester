const deleteDialog = document.querySelector('[data-report-delete]');
if (deleteDialog && typeof deleteDialog.showModal === 'function') {
  deleteDialog.close();
  deleteDialog.showModal();
  document.querySelector('[data-delete-backdrop]')?.remove();
  deleteDialog.addEventListener('cancel', event => {
    event.preventDefault();
    window.location.assign(deleteDialog.dataset.cancelUrl);
  });
}
