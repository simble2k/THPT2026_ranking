const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';

const searchForm = document.getElementById('search-form');
const resultSection = document.getElementById('result-section');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const tabBtns = document.querySelectorAll('.tab-btn');

let currentData = null;

searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const candidateId = document.getElementById('candidate-id').value;
    
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/api/candidate/${candidateId}`);
        if (!response.ok) {
            if (response.status === 404) throw new Error('Không tìm thấy Số báo danh này.');
            throw new Error('Đã có lỗi xảy ra. Vui lòng thử lại sau.');
        }
        
        currentData = await response.json();
        renderResult(currentData);
        hideLoading();
    } catch (err) {
        showError(err.message);
    }
});

function renderResult(data) {
    document.getElementById('display-id').textContent = `SBD: ${data.candidate_id}`;
    document.getElementById('display-location').textContent = `${data.province_name} | ${data.region_name}`;
    
    // Render individual scores
    const grid = document.getElementById('scores-grid');
    grid.innerHTML = '';
    const subjectLabels = {
        math: 'Toán',
        literature: 'Văn',
        foreign_language: 'N.Ngữ',
        physics: 'Lý',
        chemistry: 'Hóa',
        biology: 'Sinh',
        history: 'Sử',
        geography: 'Địa',
        civic_education: 'GDCD'
    };

    for (const [key, label] of Object.entries(subjectLabels)) {
        const val = data.scores[key];
        if (val !== null) {
            grid.innerHTML += `
                <div class="score-card">
                    <div class="score-label">${label}</div>
                    <div class="score-value">${val}</div>
                </div>
            `;
        }
    }

    // Default tab
    switchTab('nationwide');
    resultSection.classList.remove('hidden');
}

function switchTab(scope) {
    tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === scope);
    });

    const content = document.getElementById('ranking-content');
    let htmlBuffer = ''; // Build the string once to avoid DOM thrashing

    currentData.blocks.forEach(block => {
        const info = block[scope];
        htmlBuffer += `
            <div class="block-card">
                <h3>Khối ${block.block}: ${block.score}</h3>
                <div class="rank-display">
                    <div>
                        <div class="score-label">Thứ hạng</div>
                        <div class="rank-value">${info.rank.toLocaleString()} / ${info.total_candidates.toLocaleString()}</div>
                    </div>
                    <div class="percentile-tag">Top ${ (100 - info.percentile).toFixed(2) }%</div>
                </div>
            </div>
        `;
    });
    
    content.innerHTML = htmlBuffer;
}

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function showLoading() {
    loading.classList.remove('hidden');
    resultSection.classList.add('hidden');
    error.classList.add('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}

function showError(msg) {
    error.textContent = msg;
    error.classList.remove('hidden');
    loading.classList.add('hidden');
}
