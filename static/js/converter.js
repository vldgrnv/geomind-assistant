(function () {
    function initConverter() {
        const selIn = document.getElementById('conv-input-select');
        const selOut = document.getElementById('conv-output-select');
        const hintEl = document.getElementById('conv-hint');
        const openBtn = document.getElementById('conv-open-btn');
        const overlay = document.getElementById('conv-modal-overlay');
        const modalPair = document.getElementById('conv-modal-pair');
        const fileInput = document.getElementById('conv-file-input');
        const modalSubmit = document.getElementById('conv-modal-submit');
        const modalCancel = document.getElementById('conv-modal-cancel');
        const modalStatus = document.getElementById('conv-modal-status');
        const downloadLink = document.getElementById('conv-download-link');

        if (!selIn || !selOut || !hintEl || !openBtn || !overlay) return;

        /** База URL API после успешного probe (относительная '' или абсолютная с хостом:порт) */
        let resolvedApiBase;
        let resolvePromise;

        /**
         * Определяет, куда реально ходить за /api/*.
         * Если страница открыта с порта фронтенда (5173, 63342 и т.д.), относительный /api/convert даёт 404 — пробуем тот же hostname:8000 и loopback.
         */
        async function ensureResolvedApiBase() {
            if (resolvedApiBase !== undefined) return resolvedApiBase;
            if (resolvePromise) {
                await resolvePromise;
                return resolvedApiBase;
            }

            resolvePromise = (async function probe() {
                const meta = document.querySelector('meta[name="geomind-api-base"]');
                if (meta && meta.content && meta.content.trim()) {
                    resolvedApiBase = meta.content.trim().replace(/\/$/, '');
                    return;
                }

                const loc = window.location;
                if (loc.protocol === 'file:') {
                    resolvedApiBase = 'http://127.0.0.1:8000';
                    return;
                }

                const candidates = [];

                candidates.push({ base: '', probe: '/api/convert/options' });

                if (loc.hostname && loc.port && loc.port !== '8000') {
                    const b = loc.protocol + '//' + loc.hostname + ':8000';
                    candidates.push({ base: b, probe: b + '/api/convert/options' });
                }

                if (!loc.port || loc.port === '') {
                    const b = loc.protocol + '//' + loc.hostname + ':8000';
                    candidates.push({ base: b, probe: b + '/api/convert/options' });
                }

                if (loc.hostname === 'localhost') {
                    candidates.push({
                        base: 'http://127.0.0.1:8000',
                        probe: 'http://127.0.0.1:8000/api/convert/options',
                    });
                }
                if (loc.hostname === '127.0.0.1') {
                    candidates.push({
                        base: 'http://localhost:8000',
                        probe: 'http://localhost:8000/api/convert/options',
                    });
                }

                const tried = new Set();
                for (const c of candidates) {
                    if (tried.has(c.probe)) continue;
                    tried.add(c.probe);
                    try {
                        const res = await fetch(c.probe, { method: 'GET', cache: 'no-store' });
                        if (res.ok) {
                            resolvedApiBase = c.base;
                            return;
                        }
                    } catch (_e) {}
                }

                resolvedApiBase = '';
            })();

            await resolvePromise;
            resolvePromise = null;
            return resolvedApiBase;
        }

        function apiUrl(path) {
            const base = resolvedApiBase === undefined ? '' : resolvedApiBase;
            const p = path.startsWith('/') ? path : '/' + path;
            if (!base) return p;
            return base + p;
        }

        let optionsData = null;
        let lastBlobUrl = null;

        function token() {
            return localStorage.getItem('token');
        }

        function inputMeta(key) {
            if (!optionsData || !optionsData.inputs) return null;
            return optionsData.inputs.find((x) => x.key === key);
        }

        function rebuildOutputOptions() {
            if (!optionsData) return;
            const ik = selIn.value;
            const allowed = (optionsData.outputs_by_input[ik] || []).slice();
            const labels = optionsData.output_labels || {};
            selOut.innerHTML = '';
            allowed.forEach((ok) => {
                const opt = document.createElement('option');
                opt.value = ok;
                opt.textContent = labels[ok] || ok;
                selOut.appendChild(opt);
            });
            updateHintFromOutput();
        }

        function updateHintFromOutput() {
            if (!optionsData) return;
            const ik = selIn.value;
            const ok = selOut.value;
            const hi = inputMeta(ik);
            const oh = optionsData.output_hints || {};
            let hint = hi && hi.hint ? hi.hint : '';
            if (ok && oh[ok]) {
                hint = hint ? hint + ' · ' + oh[ok] : oh[ok];
            }
            hintEl.textContent = hint || '';
        }

        async function loadOptions() {
            hintEl.textContent = 'Загрузка списков…';
            await ensureResolvedApiBase();

            let data = null;
            try {
                const res = await fetch(apiUrl('/api/convert/options'), { cache: 'no-store' });
                if (res.ok) data = await res.json();
            } catch (_e) {}

            if (!data) {
                try {
                    const res = await fetch('/static/converter-options.json', { cache: 'no-store' });
                    if (res.ok) data = await res.json();
                } catch (_e) {}
            }

            if (!data) {
                hintEl.textContent =
                    'Не удалось загрузить форматы. Запустите backend (uvicorn) и откройте ЛК с того же хоста, что и API (часто http://127.0.0.1:8000/static/dashboard.html). Для нестандартного адреса добавьте метатег geomind-api-base с полным URL API.';
                return;
            }

            optionsData = data;
            selIn.innerHTML = '';
            if (!optionsData.inputs || !optionsData.inputs.length) {
                hintEl.textContent = 'Список форматов пуст.';
                return;
            }
            optionsData.inputs.forEach((inp) => {
                const opt = document.createElement('option');
                opt.value = inp.key;
                opt.textContent = inp.label;
                selIn.appendChild(opt);
            });
            rebuildOutputOptions();
        }

        function openModal() {
            if (!token()) {
                window.location.href = '/static/login.html';
                return;
            }
            if (!optionsData || !selIn.value || !selOut.value) return;
            modalStatus.textContent = '';
            modalSubmit.disabled = true;
            fileInput.value = '';
            downloadLink.hidden = true;
            downloadLink.removeAttribute('href');
            if (lastBlobUrl) {
                URL.revokeObjectURL(lastBlobUrl);
                lastBlobUrl = null;
            }

            const labels = optionsData.output_labels || {};
            const il = inputMeta(selIn.value);
            modalPair.textContent =
                (il ? il.label : selIn.value) + ' → ' + (labels[selOut.value] || selOut.value);

            overlay.hidden = false;
            fileInput.focus();
        }

        function closeModal() {
            overlay.hidden = true;
            modalSubmit.disabled = true;
            modalStatus.textContent = '';
        }

        function parseFilenameFromDisposition(cd) {
            if (!cd) return 'download';
            const mStar = /filename\*=UTF-8''([^;]+)/i.exec(cd);
            if (mStar) return decodeURIComponent(mStar[1].trim());
            const m = /filename="([^"]+)"/i.exec(cd);
            if (m) return m[1];
            const m2 = /filename=([^;\s]+)/i.exec(cd);
            return m2 ? m2[1].replace(/"/g, '') : 'download';
        }

        async function runConvert() {
            const t = token();
            if (!t) {
                window.location.href = '/static/login.html';
                return;
            }
            const f = fileInput.files && fileInput.files[0];
            if (!f) return;

            await ensureResolvedApiBase();

            modalSubmit.disabled = true;
            modalStatus.textContent = 'Конвертация…';

            const fd = new FormData();
            fd.append('input_format', selIn.value);
            fd.append('output_format', selOut.value);
            fd.append('file', f);

            try {
                const res = await fetch(apiUrl('/api/convert'), {
                    method: 'POST',
                    headers: { Authorization: 'Bearer ' + t },
                    body: fd,
                });

                if (res.status === 401) {
                    window.location.href = '/static/login.html';
                    return;
                }

                if (!res.ok) {
                    let msg = 'Ошибка сервера (' + res.status + ')';
                    try {
                        const err = await res.json();
                        if (err.detail) msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
                    } catch (_) {
                        const txt = await res.text();
                        if (txt && txt.length < 400) msg = txt;
                    }
                    modalStatus.textContent = msg;
                    modalSubmit.disabled = false;
                    return;
                }

                const blob = await res.blob();
                const name = parseFilenameFromDisposition(res.headers.get('Content-Disposition'));
                if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
                lastBlobUrl = URL.createObjectURL(blob);
                downloadLink.href = lastBlobUrl;
                downloadLink.download = name;
                downloadLink.hidden = false;
                modalStatus.textContent = 'Готово — можно скачать файл.';
                modalSubmit.disabled = false;
            } catch (e) {
                modalStatus.textContent = 'Ошибка сети или сервера.';
                modalSubmit.disabled = false;
            }
        }

        selIn.addEventListener('change', rebuildOutputOptions);
        selOut.addEventListener('change', updateHintFromOutput);

        openBtn.addEventListener('click', () => openModal());
        modalCancel.addEventListener('click', () => closeModal());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        fileInput.addEventListener('change', () => {
            modalSubmit.disabled = !fileInput.files || fileInput.files.length === 0;
        });

        modalSubmit.addEventListener('click', () => runConvert());

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !overlay.hidden) closeModal();
        });

        loadOptions();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initConverter);
    } else {
        initConverter();
    }
})();
