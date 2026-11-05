(() => {
    const search = document.getElementById('completion-search');
    if (search) {
        const cards = [...document.querySelectorAll('[data-completion-project]')];
        search.addEventListener('input', () => {
            const query = search.value.trim().toLocaleLowerCase();
            cards.forEach(card => {
                card.hidden = !card.textContent.toLocaleLowerCase().includes(query);
            });
        });
    }

    document.querySelectorAll('[data-print-document]').forEach(button => {
        button.addEventListener('click', () => window.print());
    });

    document.querySelectorAll('select[name="category"]').forEach(select => {
        const form = select.closest('form');
        const issue = form && form.querySelector('select[name="issue_id"]');
        if (!issue) return;
        const update = () => {
            issue.required = select.value === 'issue_evidence';
            issue.disabled = select.value !== 'issue_evidence';
            if (issue.disabled) issue.value = '';
        };
        select.addEventListener('change', update);
        update();
    });
})();
