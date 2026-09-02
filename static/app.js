const API = '';
let currentAudio = null;

// --- 页面切换 ---
function showListView() {
    document.getElementById('list-view').style.display = '';
    document.getElementById('training-view').style.display = 'none';
    loadAudioList();
}

function showTrainingView() {
    document.getElementById('list-view').style.display = 'none';
    document.getElementById('training-view').style.display = '';
}

// --- 音频列表 ---
async function loadAudioList() {
    const resp = await fetch(`${API}/api/audio_list`);
    const list = await resp.json();
    const container = document.getElementById('audio-list');

    if (list.length === 0) {
        container.innerHTML = '<div class="empty">还没有上传音频，上传一个开始训练吧</div>';
        return;
    }

    container.innerHTML = list.map(item => `
        <div class="audio-item" onclick="loadAudio('${item.audio_id}')">
            <div class="audio-item-info">
                <span class="audio-item-name">${item.audio_name}</span>
                <span class="audio-item-meta">${item.segment_count} 句 · ${item.created_at}</span>
            </div>
            <button class="delete-btn" onclick="deleteAudio(event, '${item.audio_id}')">删除</button>
            <span class="audio-item-arrow">›</span>
        </div>
    `).join('');
}

// --- 删除音频 ---
async function deleteAudio(event, audioId) {
    event.stopPropagation();
    if (!confirm('确定删除这条音频吗？')) return;

    const resp = await fetch(`${API}/api/audio/${audioId}`, { method: 'DELETE' });
    if (resp.ok) {
        loadAudioList();
    } else {
        alert('删除失败');
    }
}

// --- 上传 ---
document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('file-input');
    const btn = document.getElementById('upload-btn');
    const status = document.getElementById('upload-status');

    if (!fileInput.files[0]) return;

    btn.disabled = true;
    btn.textContent = '解析中...';
    status.textContent = '正在上传并识别，这可能需要几十秒，请耐心等待';

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const resp = await fetch(`${API}/api/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '上传失败');
        }

        const data = await resp.json();
        status.textContent = `解析完成，共 ${data.segments.length} 句`;
        fileInput.value = '';
        loadAudioList();
    } catch (err) {
        status.textContent = `错误: ${err.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = '上传并解析';
    }
});

// --- 加载音频训练页 ---
async function loadAudio(audioId) {
    showTrainingView();
    const resp = await fetch(`${API}/api/audio/${audioId}`);
    const data = await resp.json();
    currentAudio = data;

    document.getElementById('training-title').textContent = data.audio_name;

    const player = document.getElementById('audio-player');
    player.src = `${API}/api/audio_file/${data.audio_path}`;

    const container = document.getElementById('sentences-container');
    container.innerHTML = data.segments.map(seg => `
        <div class="sentence-card" id="sentence-${seg.id}">
            <div class="sentence-header">
                <span class="sentence-index">${seg.id}</span>
                <button class="play-btn" onclick="playSentence(${seg.id})">播放</button>
                <div class="sentence-controls">
                    <button class="toggle-btn" onclick="toggleText(${seg.id})">显示原文</button>
                    <button class="toggle-btn" onclick="toggleTranslation(${seg.id})">显示翻译</button>
                </div>
            </div>
            <div class="sentence-text hidden" id="text-${seg.id}">${seg.text}</div>
            <div class="sentence-translation hidden" id="translation-${seg.id}">${seg.translation}</div>
        </div>
    `).join('');
}

// --- 播放单句 ---
function playSentence(id) {
    const seg = currentAudio.segments.find(s => s.id === id);
    if (!seg) return;

    const player = document.getElementById('audio-player');
    player.currentTime = seg.start_time;
    player.play();

    // 高亮当前播放的按钮
    document.querySelectorAll('.play-btn').forEach(b => {
        b.classList.remove('playing');
        b.textContent = '播放';
    });
    const btn = document.querySelector(`#sentence-${id} .play-btn`);
    btn.classList.add('playing');
    btn.textContent = '播放中';

    // 播放到 end_time 自动暂停
    const stopAt = seg.end_time;
    const onTimeUpdate = () => {
        if (player.currentTime >= stopAt) {
            player.pause();
            player.removeEventListener('timeupdate', onTimeUpdate);
            btn.classList.remove('playing');
            btn.textContent = '播放';
        }
    };
    player.addEventListener('timeupdate', onTimeUpdate);
}

// --- 显示/隐藏原文 ---
function toggleText(id) {
    const el = document.getElementById(`text-${id}`);
    const btn = event.target;
    el.classList.toggle('hidden');
    if (el.classList.contains('hidden')) {
        btn.classList.remove('active');
        btn.textContent = '显示原文';
    } else {
        btn.classList.add('active');
        btn.textContent = '隐藏原文';
    }
}

// --- 显示/隐藏翻译 ---
function toggleTranslation(id) {
    const el = document.getElementById(`translation-${id}`);
    const btn = event.target;
    el.classList.toggle('hidden');
    if (el.classList.contains('hidden')) {
        btn.classList.remove('active');
        btn.textContent = '显示翻译';
    } else {
        btn.classList.add('active');
        btn.textContent = '隐藏翻译';
    }
}

// --- 返回按钮 ---
document.getElementById('back-btn').addEventListener('click', showListView);

// --- 初始化 ---
loadAudioList();
