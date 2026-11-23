// Project-specific JS (complete project action + toggle participate)
(function(){
  document.addEventListener("DOMContentLoaded", function() {
    const completeBtn = document.getElementById("complete-project-btn");
    if (completeBtn) {
      completeBtn.addEventListener("click", async function(e) {
        e.preventDefault();
        completeBtn.disabled = true;
        try {
          const response = await fetch(completeBtn.dataset.url, {
            method: "POST",
            headers: {
              "X-CSRFToken": document.querySelector('[name="csrfmiddlewaretoken"]').value,
            },
          });
          const data = await response.json().catch(() => null);
          if (!response.ok || data?.status !== "ok" || data.project_status !== "closed") {
            throw new Error(data?.error || `Не удалось завершить проект (${response.status}). Обновите страницу и повторите попытку.`);
          }
          const statusEl = document.querySelector(".project-status-black");
          if (statusEl) statusEl.textContent = "Завершён";
          completeBtn.remove();
          if (window.toast) window.toast("Проект завершён", { type: 'info' });
        } catch (error) {
          const message = error instanceof TypeError ? "Ошибка сети. Повторите попытку." : error.message;
          if (window.toast) window.toast(message, { type: 'error' });
          else window.alert(message);
          completeBtn.disabled = false;
        }
      });
    }

    const participateBtn = document.getElementById("participate-btn");
    if (participateBtn) {
      participateBtn.addEventListener("click", async function(e) {
        e.preventDefault();
        if (participateBtn.disabled) return;
        participateBtn.disabled = true;
        try {
          const response = await fetch(participateBtn.dataset.url, {
            method: "POST",
            headers: {
              "X-CSRFToken": document.querySelector('[name="csrfmiddlewaretoken"]').value,
            },
          });
          const data = await response.json().catch(() => null);
          if (!response.ok || data?.status !== "ok" || typeof data.participating !== "boolean") {
            throw new Error(data?.error || `Не удалось изменить участие (${response.status}). Обновите страницу и повторите попытку.`);
          }
          participateBtn.textContent = data.participating ? "Отказаться от участия" : "Участвовать";
          // Шаблон заново покажет актуальный список участников и доступные действия.
          window.location.reload();
        } catch (error) {
          const message = error instanceof TypeError ? "Ошибка сети. Повторите попытку." : error.message;
          if (window.toast) window.toast(message, { type: 'error' });
          else window.alert(message);
          participateBtn.disabled = false;
        }
      });
    }
  });
})();
