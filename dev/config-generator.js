// 全局變數
let songCounter = 0;
const MAX_CARDS = 40;
const MAX_SONGS = 3;
let useCardDatabase = false; // 是否成功加載卡片數據庫
let useSongDatabase = false; // 是否成功加載歌曲數據庫

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 先嘗試加載卡片數據庫和歌曲數據庫
    useCardDatabase = await loadCardDatabase();
    useSongDatabase = await loadSongDatabase();

    // 初始化卡片表格
    initCardTable();

    // 添加拖放事件監聽
    const uploadArea = document.getElementById('upload-area');

    uploadArea.addEventListener('click', () => {
        // 創建一個臨時 input 接受所有檔案類型
        const tempInput = document.createElement('input');
        tempInput.type = 'file';
        tempInput.accept = '.yaml,.yml,.csv';
        tempInput.onchange = (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                if (file.name.endsWith('.csv')) {
                    handleCSVUpload(file);
                } else {
                    handleFileUpload(file);
                }
            }
        };
        tempInput.click();
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.name.endsWith('.csv')) {
                handleCSVUpload(file);
            } else {
                handleFileUpload(file);
            }
        }
    });

    // 文件輸入變化
    document.getElementById('file-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // CSV 文件輸入變化
    document.getElementById('csv-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleCSVUpload(e.target.files[0]);
        }
    });

    // 添加一首默認歌曲
    addSong();
});

// 初始化卡片表格（生成 40 行）
function initCardTable() {
    const tbody = document.getElementById('cards-table-body');
    tbody.innerHTML = '';

    for (let i = 0; i < MAX_CARDS; i++) {
        const tr = document.createElement('tr');

        if (useCardDatabase) {
            // 使用下拉選單模式（支援搜尋）
            tr.innerHTML = `
                <td class="row-number">${i + 1}</td>
                <td>
                    <input type="text" id="char-input-${i}" list="char-list-${i}"
                           placeholder="選擇或搜尋角色..."
                           oninput="onCharacterInput(${i})"
                           autocomplete="off">
                    <datalist id="char-list-${i}"></datalist>
                </td>
                <td>
                    <input type="text" id="card-input-${i}" list="card-list-${i}"
                           placeholder="請先選擇角色"
                           oninput="onCardInput(${i})"
                           autocomplete="off"
                           disabled>
                    <datalist id="card-list-${i}"></datalist>
                </td>
                <td><input type="text" id="card-id-${i}" placeholder="自動填入" readonly></td>
                <td><input type="number" id="card-level-${i}" placeholder="滿練留空" min="1"></td>
                <td><input type="number" id="center-skill-${i}" placeholder="滿練留空" min="1"></td>
                <td><input type="number" id="skill-level-${i}" placeholder="滿練留空" min="1"></td>
            `;
        } else {
            // 降級為手動輸入模式
            tr.innerHTML = `
                <td class="row-number">${i + 1}</td>
                <td colspan="2"><input type="text" id="card-id-${i}" placeholder="卡片ID" oninput="updateCardCount(); updateAllMustCardSelects();"></td>
                <td><input type="number" id="card-level-${i}" placeholder="滿練留空" min="1"></td>
                <td><input type="number" id="center-skill-${i}" placeholder="滿練留空" min="1"></td>
                <td><input type="number" id="skill-level-${i}" placeholder="滿練留空" min="1"></td>
            `;
        }

        tbody.appendChild(tr);
    }

    // 如果使用數據庫模式，填充角色下拉選單並添加事件監聽器
    if (useCardDatabase) {
        populateCharacterSelects();

        // 為每個角色和卡片輸入框添加 change 事件監聽器
        for (let i = 0; i < MAX_CARDS; i++) {
            const charInput = document.getElementById(`char-input-${i}`);
            const cardInput = document.getElementById(`card-input-${i}`);

            if (charInput) {
                charInput.addEventListener('change', () => onCharacterInput(i));
            }
            if (cardInput) {
                cardInput.addEventListener('change', () => onCardInput(i));
            }
        }
    }

    updateCardCount();
}

// 填充所有角色下拉選單
function populateCharacterSelects() {
    const characters = getCharacterList();

    for (let i = 0; i < MAX_CARDS; i++) {
        const datalist = document.getElementById(`char-list-${i}`);
        if (!datalist) continue;

        // 清空現有選項
        datalist.innerHTML = '';

        // 添加角色選項
        characters.forEach(char => {
            const option = document.createElement('option');
            option.value = `${char.name} (${char.cardCount} 張卡)`;
            option.setAttribute('data-char-id', char.id);
            datalist.appendChild(option);
        });
    }
}

// 當角色輸入改變時
function onCharacterInput(rowIndex) {
    const charInput = document.getElementById(`char-input-${rowIndex}`);
    const cardInput = document.getElementById(`card-input-${rowIndex}`);
    const cardIdInput = document.getElementById(`card-id-${rowIndex}`);
    const cardDatalist = document.getElementById(`card-list-${rowIndex}`);

    const inputValue = charInput.value.trim();

    // 清空卡片選單和 ID
    cardDatalist.innerHTML = '';
    cardInput.value = '';
    cardIdInput.value = '';

    if (!inputValue) {
        cardInput.disabled = true;
        cardInput.placeholder = '請先選擇角色';
        updateCardCount();
        return;
    }

    // 從 datalist 中查找匹配的角色 ID
    const datalist = document.getElementById(`char-list-${rowIndex}`);
    let characterId = null;

    for (const option of datalist.options) {
        if (option.value === inputValue) {
            characterId = parseInt(option.getAttribute('data-char-id'));
            break;
        }
    }

    if (!characterId) {
        cardInput.disabled = true;
        cardInput.placeholder = '請先選擇角色';
        updateCardCount();
        return;
    }

    // 啟用卡片選單並填充選項
    cardInput.disabled = false;
    cardInput.placeholder = '選擇或搜尋卡片...';
    const cards = getCardsByCharacter(characterId);

    cards.forEach(card => {
        const option = document.createElement('option');
        option.value = formatCardName(card);
        option.setAttribute('data-card-id', card.id);
        cardDatalist.appendChild(option);
    });
}

// 當卡片輸入改變時
function onCardInput(rowIndex) {
    const cardInput = document.getElementById(`card-input-${rowIndex}`);
    const cardIdInput = document.getElementById(`card-id-${rowIndex}`);

    const inputValue = cardInput.value.trim();

    if (!inputValue) {
        cardIdInput.value = '';
        updateCardCount();
        updateAllMustCardSelects();
        return;
    }

    // 從 datalist 中查找匹配的卡片 ID
    const datalist = document.getElementById(`card-list-${rowIndex}`);
    let cardId = null;

    for (const option of datalist.options) {
        if (option.value === inputValue) {
            cardId = option.getAttribute('data-card-id');
            break;
        }
    }

    if (cardId) {
        // 檢查是否已存在相同的卡片 ID
        let isDuplicate = false;
        for (let i = 0; i < MAX_CARDS; i++) {
            if (i === rowIndex) continue; // 跳過當前行
            const existingCardId = document.getElementById(`card-id-${i}`)?.value;
            if (existingCardId && existingCardId === cardId) {
                isDuplicate = true;
                break;
            }
        }

        if (isDuplicate) {
            alert('此卡片已在卡池中，請勿重複添加');
            cardInput.value = '';
            cardIdInput.value = '';
        } else {
            cardIdInput.value = cardId;
        }
    } else {
        cardIdInput.value = '';
    }

    updateCardCount();
    updateAllMustCardSelects();
}

// 更新卡片計數
function updateCardCount() {
    let count = 0;
    for (let i = 0; i < MAX_CARDS; i++) {
        const cardId = document.getElementById(`card-id-${i}`)?.value;
        if (cardId && cardId.trim() !== '') {
            count++;
        }
    }

    const countElement = document.getElementById('card-count');
    countElement.textContent = `${count} / ${MAX_CARDS}`;

    // 更新樣式
    countElement.className = 'card-count';
    if (count >= MAX_CARDS) {
        countElement.classList.add('error');
    } else if (count >= 30) {
        countElement.classList.add('warning');
    }
}

// 獲取已填寫的卡片列表（用於必須卡片選擇）
function getFilledCards() {
    const cards = [];
    for (let i = 0; i < MAX_CARDS; i++) {
        const cardId = document.getElementById(`card-id-${i}`)?.value;
        if (cardId && cardId.trim() !== '') {
            const cardInfo = getCardById(cardId);
            if (cardInfo) {
                cards.push({
                    id: cardId,
                    name: cardInfo.name,
                    characterId: cardInfo.characterId,
                    characterName: cardInfo.characterName,
                    rarity: cardInfo.rarity
                });
            }
        }
    }
    return cards;
}

// 更新歌曲添加按鈕狀態
function updateSongButtonState() {
    const songCount = document.querySelectorAll('.song-item').length;
    const addBtn = document.getElementById('add-song-btn');
    if (songCount >= MAX_SONGS) {
        addBtn.disabled = true;
        addBtn.textContent = `已達上限（${MAX_SONGS} 首）`;
    } else {
        addBtn.disabled = false;
        addBtn.textContent = '+ 添加歌曲';
    }
}

// 添加歌曲配置
function addSong() {
    const container = document.getElementById('songs-container');
    const currentCount = document.querySelectorAll('.song-item').length;

    if (currentCount >= MAX_SONGS) {
        alert(`最多只能添加 ${MAX_SONGS} 首歌曲`);
        return;
    }

    const songId = songCounter++;
    const songDiv = document.createElement('div');
    songDiv.className = 'song-item';
    songDiv.id = `song-${songId}`;

    let songSelectHTML = '';
    if (useSongDatabase) {
        songSelectHTML = `
            <div class="form-group">
                <label>歌曲名稱</label>
                <input type="text" id="song-input-${songId}" list="song-list-${songId}"
                       placeholder="選擇或搜尋歌曲..." oninput="onSongInput(${songId})"
                       autocomplete="off">
                <datalist id="song-list-${songId}"></datalist>
            </div>
            <div class="form-group">
                <label>歌曲 ID</label>
                <input type="text" id="music-id-${songId}" placeholder="自動填入" readonly>
            </div>`;
    } else {
        songSelectHTML = `
            <div class="form-group">
                <label>歌曲 ID</label>
                <input type="text" id="music-id-${songId}" placeholder="405117">
            </div>`;
    }

    songDiv.innerHTML = `
        <div class="song-item-header">
            <h3>歌曲 #${currentCount + 1}</h3>
            <button class="remove-btn" onclick="removeSong(${songId})">移除</button>
        </div>
        <div class="input-row">
            ${songSelectHTML}
            <div class="form-group">
                <label>難度</label>
                <select id="difficulty-${songId}">
                    <option value="01">Normal</option>
                    <option value="02" selected>Hard</option>
                    <option value="03">Expert</option>
                    <option value="04">Master</option>
                </select>
            </div>
            <div class="form-group">
                <label>Mastery Lv.</label>
                <input type="number" id="mastery-${songId}" value="50" min="1" max="50">
            </div>
        </div>
        <div class="form-group">
            <label>必須卡片 (All) - 最多 6 張，相同角色最多 2 張</label>
            <select id="mustcard-all-select-${songId}" onchange="addMustCard(${songId}, 'all')">
                <option value="">從卡池中選擇卡片...</option>
            </select>
            <div class="mustcard-list" id="mustcard-all-list-display-${songId}"></div>
            <input type="hidden" id="mustcards-all-${songId}">
        </div>
        <div class="form-group">
            <label>必須卡片 (Any)</label>
            <select id="mustcard-any-select-${songId}" onchange="addMustCard(${songId}, 'any')">
                <option value="">從卡池中選擇卡片...</option>
            </select>
            <div class="mustcard-list" id="mustcard-any-list-display-${songId}"></div>
            <input type="hidden" id="mustcards-any-${songId}">
        </div>
        <div class="developer-options">
            <div class="developer-options-header">
                <input type="checkbox" id="dev-options-${songId}" onchange="toggleDeveloperOptions(${songId})">
                <label for="dev-options-${songId}">開發者選項</label>
            </div>
            <div class="developer-options-content" id="dev-options-content-${songId}">
                <div class="input-row">
                    <div class="form-group">
                        <label>中心覆蓋</label>
                        <input type="text" id="center-override-${songId}" placeholder="留空使用默認">
                    </div>
                    <div class="form-group">
                        <label>顏色覆蓋</label>
                        <select id="color-override-${songId}">
                            <option value="">默認</option>
                            <option value="1">Smile (1)</option>
                            <option value="2">Pure (2)</option>
                            <option value="3">Cool (3)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Leader 指定</label>
                        <input type="text" id="leader-designation-${songId}" value="0">
                    </div>
                </div>
            </div>
        </div>
    `;

    container.appendChild(songDiv);

    // 如果使用歌曲數據庫，填充歌曲列表
    if (useSongDatabase) {
        populateSongSelect(songId);
    }

    // 填充必須卡片選擇列表
    populateMustCardSelects(songId);

    updateSongButtonState();
}

// 移除歌曲
function removeSong(songId) {
    const songDiv = document.getElementById(`song-${songId}`);
    if (songDiv) {
        songDiv.remove();
        // 更新所有歌曲的標題編號
        const allSongs = document.querySelectorAll('.song-item');
        allSongs.forEach((song, index) => {
            const header = song.querySelector('h3');
            if (header) {
                header.textContent = `歌曲 #${index + 1}`;
            }
        });
    }
    updateSongButtonState();
}

// 填充歌曲選擇列表
function populateSongSelect(songId) {
    const datalist = document.getElementById(`song-list-${songId}`);
    if (!datalist) return;

    const songs = getSongList();
    songs.forEach(song => {
        const option = document.createElement('option');
        option.value = formatSongName(song);
        option.setAttribute('data-song-id', song.id);
        datalist.appendChild(option);
    });
}

// 當歌曲輸入改變時
function onSongInput(songId) {
    const songInput = document.getElementById(`song-input-${songId}`);
    const musicIdInput = document.getElementById(`music-id-${songId}`);

    const inputValue = songInput.value.trim();

    if (!inputValue) {
        musicIdInput.value = '';
        return;
    }

    // 從 datalist 中查找匹配的歌曲 ID
    const datalist = document.getElementById(`song-list-${songId}`);
    let musicId = null;

    for (const option of datalist.options) {
        if (option.value === inputValue) {
            musicId = option.getAttribute('data-song-id');
            break;
        }
    }

    if (musicId) {
        musicIdInput.value = musicId;
    } else {
        musicIdInput.value = '';
    }
}

// 填充必須卡片選擇列表
function populateMustCardSelects(songId) {
    const cards = getFilledCards();

    ['all', 'any'].forEach(type => {
        const select = document.getElementById(`mustcard-${type}-select-${songId}`);
        if (!select) return;

        // 保留第一個默認選項，清除其他選項
        select.innerHTML = '<option value="">從卡池中選擇卡片...</option>';

        cards.forEach(card => {
            const option = document.createElement('option');
            option.value = card.id;
            option.textContent = `[${RARITY_NAMES[card.rarity] || card.rarity}] ${card.characterName} - ${card.name}`;
            option.setAttribute('data-card-id', card.id);
            option.setAttribute('data-char-id', card.characterId);
            select.appendChild(option);
        });
    });
}

// 更新所有歌曲的必須卡片選擇列表
function updateAllMustCardSelects() {
    // 找到所有歌曲
    const allSongs = document.querySelectorAll('.song-item');
    allSongs.forEach(songDiv => {
        const songId = parseInt(songDiv.id.replace('song-', ''));
        populateMustCardSelects(songId);
    });

    // 同時更新禁卡選擇列表
    populateForbiddenCardSelect();
}

// 添加必須卡片
function addMustCard(songId, type) {
    const select = document.getElementById(`mustcard-${type}-select-${songId}`);
    const hiddenInput = document.getElementById(`mustcards-${type}-${songId}`);

    const cardId = select.value;
    if (!cardId) return;

    // 獲取選中的選項
    const selectedOption = select.options[select.selectedIndex];
    const charId = selectedOption.getAttribute('data-char-id');

    // 獲取當前列表
    const currentIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()) : [];

    // 檢查是否已存在
    if (currentIds.includes(cardId)) {
        alert('此卡片已在列表中');
        select.value = '';
        return;
    }

    // 對於 All 類型，檢查限制
    if (type === 'all') {
        if (currentIds.length >= 6) {
            alert('必須卡片 (All) 最多只能添加 6 張');
            select.value = '';
            return;
        }

        // 檢查相同角色數量
        const charCount = currentIds.filter(id => {
            const card = getFilledCards().find(c => c.id === id);
            return card && card.characterId.toString() === charId;
        }).length;

        if (charCount >= 2) {
            alert('相同角色最多只能添加 2 張');
            select.value = '';
            return;
        }
    }

    // 添加到列表
    currentIds.push(cardId);
    hiddenInput.value = currentIds.join(', ');

    // 更新顯示
    updateMustCardDisplay(songId, type);

    // 重置選擇框到默認選項
    select.value = '';
}

// 移除必須卡片
function removeMustCard(songId, type, cardId) {
    const hiddenInput = document.getElementById(`mustcards-${type}-${songId}`);
    const currentIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()) : [];

    const newIds = currentIds.filter(id => id !== cardId);
    hiddenInput.value = newIds.join(', ');

    updateMustCardDisplay(songId, type);
}

// Helper: 獲取卡片顯示名稱
function getCardDisplayName(card) {
    return `[${RARITY_NAMES[card.rarity] || card.rarity}] ${card.characterName} - ${card.name}`;
}

// Helper: 創建卡片標籤元素
function createCardTagElement(displayText, removeAction) {
    const tag = document.createElement('div');
    tag.className = 'mustcard-tag';
    tag.innerHTML = `
        <span>${displayText}</span>
        <button onclick="${removeAction}">&times;</button>
    `;
    return tag;
}

// 更新必須卡片顯示
function updateMustCardDisplay(songId, type) {
    const hiddenInput = document.getElementById(`mustcards-${type}-${songId}`);
    const displayDiv = document.getElementById(`mustcard-${type}-list-display-${songId}`);

    const cardIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()) : [];
    const cards = getFilledCards();

    displayDiv.innerHTML = '';
    cardIds.forEach(cardId => {
        // 標準化 ID 為字符串進行比較
        const normalizedCardId = cardId.toString();
        let card = cards.find(c => c.id.toString() === normalizedCardId);
        
        // 如果在已填寫的卡片中找不到，嘗試直接從資料庫查詢
        if (!card) {
            card = getCardById(normalizedCardId);
        }

        if (card) {
            const displayText = getCardDisplayName(card);
            const removeAction = `removeMustCard(${songId}, '${type}', '${cardId}')`;
            displayDiv.appendChild(createCardTagElement(displayText, removeAction));
        }
    });
}

// 切換開發者選項
function toggleDeveloperOptions(songId) {
    const checkbox = document.getElementById(`dev-options-${songId}`);
    const content = document.getElementById(`dev-options-content-${songId}`);

    if (checkbox.checked) {
        content.classList.add('active');
    } else {
        content.classList.remove('active');
    }
}

// 切換進階配置
function toggleAdvancedOptions() {
    const checkbox = document.getElementById('advanced-toggle');
    const content = document.getElementById('advanced-content');

    if (checkbox.checked) {
        content.classList.add('active');
    } else {
        content.classList.remove('active');
    }
}

// 填充禁卡選擇列表
function populateForbiddenCardSelect() {
    const cards = getFilledCards();
    const select = document.getElementById('forbidden-card-select');
    if (!select) return;

    // 保留第一個默認選項，清除其他選項
    select.innerHTML = '<option value="">從卡池中選擇卡片...</option>';

    cards.forEach(card => {
        const option = document.createElement('option');
        option.value = card.id;
        option.textContent = `[${RARITY_NAMES[card.rarity] || card.rarity}] ${card.characterName} - ${card.name}`;
        option.setAttribute('data-card-id', card.id);
        select.appendChild(option);
    });
}

// 添加禁卡
function addForbiddenCard() {
    const select = document.getElementById('forbidden-card-select');
    const hiddenInput = document.getElementById('optimizer-forbidden-cards');

    const cardId = select.value;
    if (!cardId) return;

    // 獲取當前列表
    const currentIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()) : [];

    // 檢查是否已存在
    if (currentIds.includes(cardId)) {
        alert('此卡片已在禁卡列表中');
        select.value = '';
        return;
    }

    // 添加到列表
    currentIds.push(cardId);
    hiddenInput.value = currentIds.join(', ');

    // 更新顯示
    updateForbiddenCardsDisplay();

    // 重置選擇框到默認選項
    select.value = '';
}

// 移除禁卡
function removeForbiddenCard(cardId) {
    const hiddenInput = document.getElementById('optimizer-forbidden-cards');
    const currentIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()) : [];

    // 移除卡片
    const newIds = currentIds.filter(id => id !== cardId);
    hiddenInput.value = newIds.join(', ');

    // 更新顯示
    updateForbiddenCardsDisplay();
}

// 更新禁卡顯示
function updateForbiddenCardsDisplay() {
    const hiddenInput = document.getElementById('optimizer-forbidden-cards');
    const displayDiv = document.getElementById('forbidden-cards-display');

    if (!displayDiv) return;

    const cardIds = hiddenInput.value ? hiddenInput.value.split(',').map(id => id.trim()).filter(id => id !== '') : [];

    // 清空顯示區域
    displayDiv.innerHTML = '';

    // 為每個卡片創建標籤
    cardIds.forEach(cardId => {
        let displayText = cardId;
        
        if (useCardDatabase) {
            const cardInfo = getCardById(cardId);
            if (cardInfo) {
                displayText = getCardDisplayName(cardInfo);
            }
        }
        
        const removeAction = `removeForbiddenCard('${cardId}')`;
        displayDiv.appendChild(createCardTagElement(displayText, removeAction));
    });
}

// 解析卡片 ID 列表
function parseCardIds(text) {
    if (!text || text.trim() === '') return [];

    // 分割並清理
    return text
        .split(/[\n,\s]+/)
        .map(id => id.trim())
        .filter(id => id !== '')
        .map(id => parseInt(id))
        .filter(id => !isNaN(id));
}

// 生成配置對象
function generateConfig() {
    const config = {
        output: {
            base_dir: "output",
            enable_isolation: true
        },
        songs: [],
        debug_deck_cards: null,
        card_ids: [],
        season_mode: "sukushow",  // 固定為 sukushow
        fan_levels: {},
        card_levels: {},
        batch_size: parseInt(document.getElementById('batch-size').value) || 1000000,
        num_processes: null,
        cache: {
            max_fingerprints_in_memory: 5000000,
            auto_cleanup: true,
            max_cache_age_days: 7
        }
    };

    // 從表格收集卡片和練度
    for (let i = 0; i < MAX_CARDS; i++) {
        const cardId = document.getElementById(`card-id-${i}`)?.value;

        if (cardId && cardId.trim() !== '') {
            const cardIdNum = parseInt(cardId);
            if (!isNaN(cardIdNum)) {
                config.card_ids.push(cardIdNum);

                // 檢查是否有練度配置
                const level = document.getElementById(`card-level-${i}`)?.value;
                const centerSkill = document.getElementById(`center-skill-${i}`)?.value;
                const skillLevel = document.getElementById(`skill-level-${i}`)?.value;

                // 如果有任何練度資訊，則添加到 card_levels
                if (level || centerSkill || skillLevel) {
                    config.card_levels[cardIdNum] = [
                        level ? parseInt(level) : 0,
                        centerSkill ? parseInt(centerSkill) : 0,
                        skillLevel ? parseInt(skillLevel) : 0
                    ];
                }
            }
        }
    }

    // 收集粉絲等級
    const characterIds = [1011, 1021, 1022, 1023, 1031, 1032, 1033, 1041, 1042, 1043, 1051, 1052];
    characterIds.forEach(charId => {
        const value = parseInt(document.getElementById(`fan-${charId}`).value);
        if (value && value >= 1 && value <= 10) {
            config.fan_levels[charId] = value;
        }
    });

    // 收集歌曲配置
    const songItems = document.querySelectorAll('.song-item');
    songItems.forEach(item => {
        const id = item.id.split('-')[1];
        const musicId = document.getElementById(`music-id-${id}`)?.value;

        if (musicId) {
            const song = {
                music_id: musicId,
                difficulty: document.getElementById(`difficulty-${id}`).value,
                mastery_level: parseInt(document.getElementById(`mastery-${id}`).value) || 50,
                mustcards_all: parseCardIds(document.getElementById(`mustcards-all-${id}`).value),
                mustcards_any: parseCardIds(document.getElementById(`mustcards-any-${id}`).value),
                center_override: document.getElementById(`center-override-${id}`).value || null,
                color_override: document.getElementById(`color-override-${id}`).value || null,
                leader_designation: document.getElementById(`leader-designation-${id}`).value || "0"
            };
            config.songs.push(song);
        }
    });

    // 處理 num_processes
    const numProcesses = document.getElementById('num-processes').value;
    if (numProcesses && numProcesses.trim() !== '') {
        config.num_processes = parseInt(numProcesses);
    }

    // 收集優化器配置
    config.optimizer = {
        top_n: parseInt(document.getElementById('optimizer-top-n').value) || 50000,
        show_card_names: document.getElementById('optimizer-show-names').value === 'true',
        forbidden_cards: parseCardIds(document.getElementById('optimizer-forbidden-cards').value)
    };

    return config;
}

// 生成 YAML 字符串
function generateYAML() {
    const config = generateConfig();
    const memberName = document.getElementById('member-name').value || 'example';

    let yaml = `# ============================================
# 公會成員配置 - ${memberName}
# ============================================

# 輸出目錄配置
output:
  base_dir: "output"
  enable_isolation: true       # 開啟隔離，每次運行生成獨立目錄

# 歌曲配置 (支援多首歌曲)
# 可以配置最多 3 首歌曲進行同時計算
songs:
`;

    // 生成歌曲配置
    if (config.songs && config.songs.length > 0) {
        config.songs.forEach((song, index) => {
            // 獲取歌曲名稱
            const songInfo = getSongById(song.music_id);
            const songComment = songInfo ? `   # ${songInfo.name}` : '';
            
            yaml += `  # 歌曲 ${index + 1}\n`;
            yaml += `  - music_id: "${song.music_id}"${songComment}\n`;
            yaml += `    difficulty: "${song.difficulty}"           # 難度: 01=Normal, 02=Hard, 03=Expert, 04=Master\n`;
            yaml += `    mastery_level: ${song.mastery_level}          # Mastery 等級 (1-50)\n`;
            yaml += `    mustcards_all: [${song.mustcards_all.join(',')}]   # 必須同時使用的卡片 (All，最多6張，同角色最多2張)\n`;
            yaml += `    mustcards_any: [${song.mustcards_any.join(',')}]   # 至少使用其中一張的卡片 (Any)\n`;
            yaml += `    center_override: ${song.center_override || 'null'}      # 強制指定中心技能 ID (留空自動)\n`;
            yaml += `    color_override: ${song.color_override || 'null'}       # 強制指定隊伍顏色: 1=Smile, 2=Pure, 3=Cool (留空自動)\n`;
            yaml += `    leader_designation: "${song.leader_designation}"  # Leader 指定 (通常為 "0")\n`;
            if (index < config.songs.length - 1) {
                yaml += `\n`;
            }
        });
    } else {
        yaml += `  # 範例配置 (取消註釋以使用):\n`;
        yaml += `  # - music_id: "405119"        # 歌曲 ID，可在遊戲中查看\n`;
        yaml += `  #   difficulty: "02"           # 難度: 01=Normal, 02=Hard, 03=Expert, 04=Master\n`;
        yaml += `  #   mastery_level: 50          # Mastery 等級 (1-50)\n`;
        yaml += `  #   mustcards_all: []          # 必須同時使用的卡片 (All，最多6張，同角色最多2張)\n`;
        yaml += `  #   mustcards_any: []          # 至少使用其中一張的卡片 (Any)\n`;
        yaml += `  #   center_override: null      # 強制指定中心技能 ID (留空自動)\n`;
        yaml += `  #   color_override: null       # 強制指定隊伍顏色 (留空自動)\n`;
        yaml += `  #   leader_designation: "0"    # Leader 指定\n`;
    }

    yaml += `\n`;

    // Debug 卡組
    yaml += `# Debug 卡組 (可選，用於單卡組測試)\n`;
    yaml += `# 格式: [卡片ID1, 卡片ID2, ..., 卡片ID9]\n`;
    yaml += `# 留空則進行完整計算\n`;
    yaml += `debug_deck_cards: null\n\n`;

    // 卡池
    yaml += `# ${memberName} 的卡池\n`;
    yaml += `# 列出所有擁有的卡片 ID (最多 40 張)\n`;
    yaml += `# 可以在遊戲中或卡片資料庫中查詢卡片 ID\n`;
    yaml += `card_ids:\n`;
    if (config.card_ids && config.card_ids.length > 0) {
        config.card_ids.forEach(id => {
            // 獲取卡片信息
            const cardInfo = getCardById(id.toString());
            let comment = '';
            if (cardInfo) {
                const rarityName = RARITY_NAMES[cardInfo.rarity] || `★${cardInfo.rarity}`;
                comment = `   # [${rarityName}] ${cardInfo.characterName} - ${cardInfo.name}`;
            }
            yaml += ` - ${id}${comment}\n`;
        });
    } else {
        yaml += ` # - 1011501   # [UR] 大賀美 沙知 - 卡片名稱\n`;
        yaml += ` # - 1021523   # [UR] 乙宗 梢 - 卡片名稱\n`;
        yaml += ` # ...\n`;
    }

    yaml += `\n# 遊戲模式 (固定為 sukushow)\n`;
    yaml += `season_mode: "sukushow"\n\n`;

    // 粉絲等級
    const fanLevelFullNames = {
        1011: '大賀美 沙知',
        1021: '乙宗 梢',
        1022: '夕霧 綴理',
        1023: '藤島 慈',
        1031: '日野下 花帆',
        1032: '村野 さやか',
        1033: '大沢 瑠璃乃',
        1041: '百生 吟子',
        1042: '徒町 小鈴',
        1043: '安養寺 姫芽',
        1051: '桂城 泉',
        1052: 'セラス 柳田 リリエンフェルト'
    };

    yaml += `# ${memberName} 的粉絲等級\n`;
    yaml += `# 範圍: 1-10，影響對應角色卡片的能力加成\n`;
    yaml += `fan_levels:\n`;
    const characterIds = [1011, 1021, 1022, 1023, 1031, 1032, 1033, 1041, 1042, 1043, 1051, 1052];
    characterIds.forEach(charId => {
        const level = config.fan_levels[charId] || 0;
        const fullName = fanLevelFullNames[charId] || '';
        yaml += `  ${charId}: ${level}   # ${fullName}\n`;
    });

    // 卡片練度
    yaml += `\n# 特定卡牌練度覆蓋 (如果有未滿練的卡)\n`;
    yaml += `# 格式: card_id: [等級, 中心技能等級, 技能等級]\n`;
    yaml += `# 滿練卡片可以不填寫或移除，系統會自動使用滿練數值\n`;
    yaml += `# 等級: 通常最大 120-140 (依稀有度而定)\n`;
    yaml += `# 中心技能等級: 最大值依卡片而定 (通常 1-14)\n`;
    yaml += `# 技能等級: 最大值依卡片而定 (通常 1-12)\n`;
    yaml += `card_levels:\n`;
    if (config.card_levels && Object.keys(config.card_levels).length > 0) {
        Object.entries(config.card_levels).forEach(([cardId, levels]) => {
            yaml += `  ${cardId}: [${levels.join(',')}]\n`;
        });
    } else {
        yaml += `  # 範例 (未滿練的卡片):\n`;
        yaml += `  # 1011501: [120, 10, 5]\n`;
        yaml += `  # 1021523: [100, 8, 3]\n`;
    }

    yaml += `\n# 批次大小 (影響計算效率，建議保持預設值)\n`;
    yaml += `batch_size: ${config.batch_size}\n\n`;
    
    yaml += `# CPU 核心數 (null = 使用全部核心，或指定數字如 4)\n`;
    yaml += `num_processes: ${config.num_processes || 'null'}\n\n`;

    yaml += `# 快取配置 (建議保持預設值)\n`;
    yaml += `cache:\n`;
    yaml += `  max_fingerprints_in_memory: ${config.cache.max_fingerprints_in_memory}  # 記憶體中最多保存的指紋數\n`;
    yaml += `  auto_cleanup: ${config.cache.auto_cleanup}                # 自動清理舊快取\n`;
    yaml += `  max_cache_age_days: ${config.cache.max_cache_age_days}                    # 快取保存天數\n\n`;

    yaml += `# 優化器配置 (用於 multi_optimizer_2.py)\n`;
    yaml += `optimizer:\n`;
    yaml += `  top_n: ${config.optimizer.top_n}                 # 每首歌保留得分排名前 N 名的卡組\n`;
    yaml += `  show_card_names: ${config.optimizer.show_card_names}        # 在輸出中顯示卡牌名稱\n`;
    yaml += `  forbidden_cards: [${config.optimizer.forbidden_cards.join(', ')}]          # 禁止使用的卡牌 ID 列表 (三面均生效)\n`;
    if (config.optimizer.forbidden_cards.length === 0) {
        yaml += `                               # 範例: [1011501, 1052506]  # 禁用特定卡牌\n`;
    }

    return yaml;
}

// 下載配置文件
function downloadConfig() {
    try {
        const yamlContent = generateYAML();
        const memberName = document.getElementById('member-name').value || 'example';
        const filename = `member-${memberName}.yaml`;

        const blob = new Blob([yamlContent], { type: 'text/yaml;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        alert(`配置文件已下載: ${filename}`);
    } catch (error) {
        alert('生成配置文件時出錯: ' + error.message);
        console.error(error);
    }
}

// 複製到剪貼板
function copyToClipboard() {
    try {
        const yamlContent = generateYAML();
        navigator.clipboard.writeText(yamlContent).then(() => {
            alert('配置已複製到剪貼板！');
        }).catch(() => {
            // 降級方案
            const textarea = document.createElement('textarea');
            textarea.value = yamlContent;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                alert('配置已複製到剪貼板！');
            } catch (e) {
                alert('無法複製到剪貼板，請手動複製');
            }
            document.body.removeChild(textarea);
        });
    } catch (error) {
        alert('複製配置時出錯: ' + error.message);
        console.error(error);
    }
}

// 處理文件上傳
function handleFileUpload(file) {
    const reader = new FileReader();

    reader.onload = (e) => {
        try {
            const yamlContent = e.target.result;
            const config = jsyaml.load(yamlContent);

            // 填充表單
            loadConfigToForm(config);

            // 從文件名提取成員名稱
            const filename = file.name.replace(/\.(yaml|yml)$/, '');
            const match = filename.match(/member-(.+)/);
            if (match) {
                document.getElementById('member-name').value = match[1];
            }

            alert('配置文件已成功載入！');
        } catch (error) {
            alert('解析配置文件時出錯: ' + error.message);
            console.error(error);
        }
    };

    reader.readAsText(file);
}

// 處理 CSV 文件上傳
function handleCSVUpload(file) {
    const reader = new FileReader();

    reader.onload = (e) => {
        try {
            const csvContent = e.target.result;
            parseCSVAndFillCards(csvContent);
            alert('CSV 卡池已成功匯入！');
        } catch (error) {
            alert('解析 CSV 文件時出錯: ' + error.message);
            console.error(error);
        }
    };

    reader.readAsText(file, 'UTF-8');
}

// 解析 CSV 並填充卡片表格
function parseCSVAndFillCards(csvContent) {
    // 分割行
    const lines = csvContent.split('\n').map(line => line.trim()).filter(line => line);
    
    if (lines.length < 2) {
        throw new Error('CSV 文件格式不正確');
    }

    // 跳過標題行，從第二行開始
    const dataLines = lines.slice(1);
    
    // 清空現有卡片
    for (let i = 0; i < MAX_CARDS; i++) {
        if (useCardDatabase) {
            const charInput = document.getElementById(`char-input-${i}`);
            const cardInput = document.getElementById(`card-input-${i}`);
            if (charInput) charInput.value = '';
            if (cardInput) {
                cardInput.value = '';
                cardInput.disabled = true;
            }
        }
        document.getElementById(`card-id-${i}`).value = '';
        document.getElementById(`card-level-${i}`).value = '';
        document.getElementById(`center-skill-${i}`).value = '';
        document.getElementById(`skill-level-${i}`).value = '';
    }

    let cardIndex = 0;
    const notFoundCards = [];
    const songData = { A: null, B: null, C: null };

    for (const line of dataLines) {
        if (cardIndex >= MAX_CARDS) {
            console.warn(`已達到最大卡片數量 (${MAX_CARDS})，忽略剩餘卡片`);
            break;
        }

        // 使用正規表達式分割 CSV，處理包含逗號的引號字段
        const fields = parseCSVLine(line);
        
        // 跳過空行或無效行
        if (fields.length < 6) continue;
        
        // 先處理一般卡片（列 0-5）
        let characterName = fields[0].trim();
        let cardId = fields[2].trim();
        let level = fields[3].trim();
        let centerSkill = fields[4].trim();
        let skillLevel = fields[5].trim();
        
        // 檢查列 7-11 是歌曲資訊還是 DR 卡資訊
        // 歌曲：列7=A/B/C, 列8=50, 列9=難度, 列10=歌曲ID
        // DR卡：列7=角色名, 列8=卡片名, 列9=等級, 列10=C位, 列11=主技能, 列12=ID
        if (fields.length >= 11) {
            const col7 = fields[7].trim();
            
            // 如果列 7 是 A/B/C，視為歌曲資訊
            if (col7 === 'A' || col7 === 'B' || col7 === 'C') {
                const stage = col7;
                const masteryLevel = fields[8].trim();
                const difficulty = fields[9].trim();
                const musicId = fields[10].trim();
                
                if (musicId && !songData[stage]) {
                    songData[stage] = {
                        music_id: musicId,
                        difficulty: difficulty || 'Master',
                        mastery_level: masteryLevel || '50'
                    };
                }
            }
        }

        // 跳過 "- - -" 這類的佔位行
        if (characterName === '- - -' || !cardId || cardId === '') continue;

        // 跳過 DR 卡（等級為 1 1 1 的一般卡片）
        if (level === '1' && centerSkill === '1' && skillLevel === '1') {
            continue;
        }

        // 處理一般卡片

        if (useCardDatabase) {
            // 使用數據庫模式
            const cardInfo = getCardById(cardId);
            
            if (cardInfo) {
                const charInput = document.getElementById(`char-input-${cardIndex}`);
                const cardInput = document.getElementById(`card-input-${cardIndex}`);
                
                // 設置角色
                const charDatalist = document.getElementById(`char-list-${cardIndex}`);
                let charText = '';
                for (const option of charDatalist.options) {
                    if (parseInt(option.getAttribute('data-char-id')) === cardInfo.characterId) {
                        charText = option.value;
                        break;
                    }
                }
                
                if (charText) {
                    charInput.value = charText;
                    onCharacterInput(cardIndex);
                    
                    // 設置卡片
                    const cardDatalist = document.getElementById(`card-list-${cardIndex}`);
                    for (const option of cardDatalist.options) {
                        if (option.getAttribute('data-card-id') === cardId) {
                            cardInput.value = option.value;
                            break;
                        }
                    }
                    onCardInput(cardIndex);
                }
            } else {
                // 如果找不到，直接填入 ID
                document.getElementById(`card-id-${cardIndex}`).value = cardId;
                notFoundCards.push(cardId);
            }
        } else {
            // 手動模式
            document.getElementById(`card-id-${cardIndex}`).value = cardId;
        }

        // 填入練度（無論數值為何都填入）
        if (level) {
            const levelElem = document.getElementById(`card-level-${cardIndex}`);
            if (levelElem) {
                levelElem.value = level;
            }
        }
        if (centerSkill) {
            const centerElem = document.getElementById(`center-skill-${cardIndex}`);
            if (centerElem) {
                centerElem.value = centerSkill;
            }
        }
        if (skillLevel) {
            const skillElem = document.getElementById(`skill-level-${cardIndex}`);
            if (skillElem) {
                skillElem.value = skillLevel;
            }
        }

        cardIndex++;
        
        // 處理 DR 卡片（與歌曲共用欄位 7-12）
        // 只有當列 7 不是 A/B/C（歌曲標記）時才可能是 DR 卡
        // 格式：列7=角色名, 列8=卡片名, 列9=等級, 列10=C位, 列11=主技能, 列12=ID
        if (fields.length >= 13 && cardIndex < MAX_CARDS) {
            const col7 = fields[7].trim();
            
            // 確認不是歌曲資訊（A/B/C）且不是表頭（"DR"）
            if (col7 && col7 !== 'A' && col7 !== 'B' && col7 !== 'C' && col7 !== 'DR') {
                const drCharName = col7;
                const drCardName = fields[8].trim();
                const drLevel = fields[9].trim();
                const drCenter = fields[10].trim();
                const drSkill = fields[11].trim();
                let drCardId = fields[12].trim();
                
                // 處理 "- ID" 格式，提取純數字
                if (drCardId.startsWith('-')) {
                    drCardId = drCardId.substring(1).trim();
                }
                
                // 只處理有 ID 且不是 1 1 1 的 DR 卡
                if (drCardId && drCardId !== '' && 
                    !(drLevel === '1' && drCenter === '1' && drSkill === '1')) {
                    
                    if (useCardDatabase) {
                        const cardInfo = getCardById(drCardId);
                        
                        if (cardInfo) {
                            const charInput = document.getElementById(`char-input-${cardIndex}`);
                            const cardInput = document.getElementById(`card-input-${cardIndex}`);
                            
                            const charDatalist = document.getElementById(`char-list-${cardIndex}`);
                            let charText = '';
                            for (const option of charDatalist.options) {
                                if (parseInt(option.getAttribute('data-char-id')) === cardInfo.characterId) {
                                    charText = option.value;
                                    break;
                                }
                            }
                            
                            if (charText) {
                                charInput.value = charText;
                                onCharacterInput(cardIndex);
                                
                                const cardDatalist = document.getElementById(`card-list-${cardIndex}`);
                                for (const option of cardDatalist.options) {
                                    if (option.getAttribute('data-card-id') === drCardId) {
                                        cardInput.value = option.value;
                                        break;
                                    }
                                }
                                onCardInput(cardIndex);
                            }
                        } else {
                            document.getElementById(`card-id-${cardIndex}`).value = drCardId;
                            notFoundCards.push(drCardId);
                        }
                    } else {
                        document.getElementById(`card-id-${cardIndex}`).value = drCardId;
                    }

                    // 填入 DR 卡練度
                    if (drLevel) {
                        const levelElem = document.getElementById(`card-level-${cardIndex}`);
                        if (levelElem) levelElem.value = drLevel;
                    }
                    if (drCenter) {
                        const centerElem = document.getElementById(`center-skill-${cardIndex}`);
                        if (centerElem) centerElem.value = drCenter;
                    }
                    if (drSkill) {
                        const skillElem = document.getElementById(`skill-level-${cardIndex}`);
                        if (skillElem) skillElem.value = drSkill;
                    }

                    cardIndex++;
                }
            }
        }
    }

    updateCardCount();
    updateAllMustCardSelects();

    // 填充歌曲資訊
    fillSongsFromCSV(songData);

    if (notFoundCards.length > 0) {
        console.warn('以下卡片 ID 在資料庫中找不到:', notFoundCards);
        alert(`成功匯入 ${cardIndex} 張卡片！\n\n注意：${notFoundCards.length} 張卡片在資料庫中找不到，已直接填入 ID。`);
    }
}

// 從 CSV 歌曲資料填充歌曲配置
function fillSongsFromCSV(songData) {
    // 清空現有歌曲
    document.getElementById('songs-container').innerHTML = '';
    songCounter = 0;

    // 按順序添加 A, B, C 面的歌曲
    const stages = ['A', 'B', 'C'];
    for (const stage of stages) {
        if (songData[stage]) {
            addSong();
            const songId = songCounter - 1;
            const song = songData[stage];

            // 使用 setTimeout 確保 DOM 元素已創建
            setTimeout(() => {
                // 填入歌曲 ID
                if (song.music_id) {
                    const musicIdElem = document.getElementById(`music-id-${songId}`);
                    if (musicIdElem) {
                        musicIdElem.value = song.music_id;
                    }
                    
                    // 如果使用歌曲資料庫，設置歌曲名稱
                    if (useSongDatabase) {
                        const songInput = document.getElementById(`song-input-${songId}`);
                        if (songInput) {
                            const songInfo = getSongById(song.music_id);
                            if (songInfo) {
                                songInput.value = formatSongName(songInfo);
                            }
                        }
                    }
                }
                
                // 填入難度
                if (song.difficulty) {
                    const difficultyElem = document.getElementById(`difficulty-${songId}`);
                    if (difficultyElem) {
                        // 將難度文字轉換為數字代碼
                        const difficultyMap = {
                            'Normal': '01',
                            'Hard': '02',
                            'Expert': '03',
                            'Master': '04'
                        };
                        const difficultyValue = difficultyMap[song.difficulty] || song.difficulty;
                        difficultyElem.value = difficultyValue;
                    }
                }
                
                // 填入歌曲等級
                if (song.mastery_level) {
                    const masteryElem = document.getElementById(`mastery-${songId}`);
                    if (masteryElem) {
                        masteryElem.value = song.mastery_level;
                    }
                }
            }, 100);  // 延遲 100ms 確保 DOM 已更新
        }
    }
}

// 解析 CSV 行（處理引號和逗號）
function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        
        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += char;
        }
    }
    
    result.push(current);
    return result;
}

// 從配置對象載入到表單
function loadConfigToForm(config) {
    // 清空現有內容
    document.getElementById('songs-container').innerHTML = '';
    songCounter = 0;

    // 清空卡片表格
    for (let i = 0; i < MAX_CARDS; i++) {
        if (useCardDatabase) {
            // 下拉選單模式（使用 input + datalist）
            const charInput = document.getElementById(`char-input-${i}`);
            const cardInput = document.getElementById(`card-input-${i}`);
            const cardDatalist = document.getElementById(`card-list-${i}`);
            if (charInput) charInput.value = '';
            if (cardInput) {
                cardInput.value = '';
                cardInput.disabled = true;
                cardInput.placeholder = '請先選擇角色';
            }
            if (cardDatalist) cardDatalist.innerHTML = '';
        }
        document.getElementById(`card-id-${i}`).value = '';
        document.getElementById(`card-level-${i}`).value = '';
        document.getElementById(`center-skill-${i}`).value = '';
        document.getElementById(`skill-level-${i}`).value = '';
    }

    // 載入卡片和練度
    if (config.card_ids && Array.isArray(config.card_ids)) {
        const maxCards = Math.min(config.card_ids.length, MAX_CARDS);
        const notFoundCards = [];

        for (let i = 0; i < maxCards; i++) {
            const cardId = config.card_ids[i];

            if (useCardDatabase) {
                // 使用數據庫模式，設置角色和卡片選單
                const cardInfo = getCardById(cardId.toString());
                if (cardInfo) {
                    const charInput = document.getElementById(`char-input-${i}`);
                    const cardInput = document.getElementById(`card-input-${i}`);

                    // 從角色 datalist 中找到對應的文字
                    const charDatalist = document.getElementById(`char-list-${i}`);
                    let charText = '';
                    for (const option of charDatalist.options) {
                        if (parseInt(option.getAttribute('data-char-id')) === cardInfo.characterId) {
                            charText = option.value;
                            break;
                        }
                    }

                    // 設置角色
                    charInput.value = charText;

                    // 觸發角色改變以填充卡片選單
                    onCharacterInput(i);

                    // 設置卡片
                    const cardDatalist = document.getElementById(`card-list-${i}`);
                    let cardText = '';
                    for (const option of cardDatalist.options) {
                        if (option.getAttribute('data-card-id') === cardId.toString()) {
                            cardText = option.value;
                            break;
                        }
                    }
                    cardInput.value = cardText;

                    // 觸發卡片改變以填入 ID
                    onCardInput(i);
                } else {
                    // 如果在數據庫中找不到，直接填入 ID 並記錄
                    document.getElementById(`card-id-${i}`).value = cardId;
                    notFoundCards.push(cardId);
                }
            } else {
                // 手動輸入模式
                document.getElementById(`card-id-${i}`).value = cardId;
            }

            // 如果有練度配置，填入
            if (config.card_levels && config.card_levels[cardId]) {
                const levels = config.card_levels[cardId];
                if (Array.isArray(levels) && levels.length === 3) {
                    if (levels[0] > 0) document.getElementById(`card-level-${i}`).value = levels[0];
                    if (levels[1] > 0) document.getElementById(`center-skill-${i}`).value = levels[1];
                    if (levels[2] > 0) document.getElementById(`skill-level-${i}`).value = levels[2];
                }
            }
        }

        // 如果有找不到的卡片，顯示警告
        if (notFoundCards.length > 0) {
            console.warn('以下卡片 ID 在資料庫中找不到:', notFoundCards);
            alert(`警告：以下卡片 ID 在資料庫中找不到，已直接填入 ID：\n${notFoundCards.join(', ')}\n\n可能原因：\n1. 資料庫尚未更新到這些卡片\n2. 卡片 ID 格式不正確\n\n這些卡片仍會保存在配置中，但無法顯示詳細資訊。`);
        }

        // 如果超過 40 張卡，顯示警告
        if (config.card_ids.length > MAX_CARDS) {
            alert(`警告：配置文件中有 ${config.card_ids.length} 張卡，但只載入了前 ${MAX_CARDS} 張。`);
        }
    }

    updateCardCount();

    // 載入粉絲等級
    if (config.fan_levels) {
        Object.entries(config.fan_levels).forEach(([charId, level]) => {
            const element = document.getElementById(`fan-${charId}`);
            if (element) {
                element.value = level;
            }
        });
    }

    // 載入歌曲
    if (config.songs && Array.isArray(config.songs)) {
        config.songs.forEach((song, index) => {
            addSong();
            const songId = index;

            // 如果使用歌曲資料庫，填入歌曲名稱
            if (useSongDatabase && song.music_id) {
                const songInput = document.getElementById(`song-input-${songId}`);
                if (songInput) {
                    const songInfo = getSongById(song.music_id);
                    if (songInfo) {
                        songInput.value = formatSongName(songInfo);
                    }
                }
            }

            if (song.music_id) document.getElementById(`music-id-${songId}`).value = song.music_id;
            if (song.difficulty) document.getElementById(`difficulty-${songId}`).value = song.difficulty;
            if (song.mastery_level) document.getElementById(`mastery-${songId}`).value = song.mastery_level;
            if (song.mustcards_all) {
                document.getElementById(`mustcards-all-${songId}`).value = song.mustcards_all.join(', ');
                updateMustCardDisplay(songId, 'all');
            }
            if (song.mustcards_any) {
                document.getElementById(`mustcards-any-${songId}`).value = song.mustcards_any.join(', ');
                updateMustCardDisplay(songId, 'any');
            }
            if (song.center_override) document.getElementById(`center-override-${songId}`).value = song.center_override;
            if (song.color_override) document.getElementById(`color-override-${songId}`).value = song.color_override;
            if (song.leader_designation) document.getElementById(`leader-designation-${songId}`).value = song.leader_designation;
        });
    }

    // 載入進階配置
    if (config.batch_size) {
        document.getElementById('batch-size').value = config.batch_size;
    }
    if (config.num_processes) {
        document.getElementById('num-processes').value = config.num_processes;
    }

    // 載入優化器配置
    if (config.optimizer) {
        if (config.optimizer.top_n !== undefined) {
            document.getElementById('optimizer-top-n').value = config.optimizer.top_n;
        }
        if (config.optimizer.show_card_names !== undefined) {
            document.getElementById('optimizer-show-names').value = config.optimizer.show_card_names ? 'true' : 'false';
        }
        if (config.optimizer.forbidden_cards && Array.isArray(config.optimizer.forbidden_cards)) {
            document.getElementById('optimizer-forbidden-cards').value = config.optimizer.forbidden_cards.join(', ');
            updateForbiddenCardsDisplay();  // 更新禁卡顯示
        }
    }
}
