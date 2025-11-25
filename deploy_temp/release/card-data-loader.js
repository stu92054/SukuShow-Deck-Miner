// 卡片數據加載器
// 從 CardDatas.json 加載並處理卡片數據

// 角色名稱映射
const CHARACTER_NAMES = {
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

// 全局變量存儲卡片數據
let cardDatabase = null;
let cardsByCharacter = {};

// 加載卡片數據
async function loadCardDatabase() {
    try {
        // 嘗試多個可能的路徑
        const possiblePaths = [
            '../Data/CardDatas.json',  // 從 web/ 訪問
            'Data/CardDatas.json',     // 從根目錄訪問
            './Data/CardDatas.json'    // 相對路徑
        ];

        let response = null;
        let lastError = null;

        for (const path of possiblePaths) {
            try {
                response = await fetch(path);
                if (response.ok) {
                    console.log(`成功從 ${path} 載入卡片數據`);
                    break;
                }
            } catch (err) {
                lastError = err;
                console.warn(`嘗試載入 ${path} 失敗:`, err.message);
            }
        }

        if (!response || !response.ok) {
            throw lastError || new Error('無法從任何路徑載入卡片數據');
        }

        cardDatabase = await response.json();

        // 按角色組織卡片
        organizeCardsByCharacter();

        console.log('卡片數據加載成功');
        return true;
    } catch (error) {
        console.error('加載卡片數據失敗:', error);
        alert('警告：無法加載卡片數據庫，將使用手動輸入模式');
        return false;
    }
}

// 按角色組織卡片
function organizeCardsByCharacter() {
    cardsByCharacter = {};

    for (const [cardId, cardData] of Object.entries(cardDatabase)) {
        const charId = cardData.CharactersId;

        // 跳過無效卡片（名稱為 ???）
        if (cardData.Name === '？？？') {
            continue;
        }

        if (!cardsByCharacter[charId]) {
            cardsByCharacter[charId] = [];
        }

        cardsByCharacter[charId].push({
            id: parseInt(cardId),
            name: cardData.Name,
            description: cardData.Description,
            rarity: cardData.Rarity
        });
    }

    // 按卡片 ID 排序（降序，新卡在前）
    for (const charId in cardsByCharacter) {
        cardsByCharacter[charId].sort((a, b) => b.id - a.id);
    }
}

// 獲取角色列表
function getCharacterList() {
    const characters = [];
    for (const [charId, charName] of Object.entries(CHARACTER_NAMES)) {
        if (cardsByCharacter[charId] && cardsByCharacter[charId].length > 0) {
            characters.push({
                id: parseInt(charId),
                name: charName,
                cardCount: cardsByCharacter[charId].length
            });
        }
    }
    return characters.sort((a, b) => a.id - b.id);
}

// 獲取指定角色的卡片列表
function getCardsByCharacter(characterId) {
    return cardsByCharacter[characterId] || [];
}

// 根據卡片 ID 獲取卡片信息
function getCardById(cardId) {
    if (!cardDatabase) {
        console.warn('卡片資料庫尚未載入');
        return null;
    }
    
    if (!cardDatabase[cardId]) {
        // 只在開發模式下顯示警告，避免正常使用時產生過多日誌
        // console.warn(`卡片 ID ${cardId} 在資料庫中找不到`);
        return null;
    }

    const cardData = cardDatabase[cardId];
    
    // 注意：不要在這裡過濾 '？？？' 卡片，因為載入配置時需要保留所有卡片資訊
    // 過濾只在 organizeCardsByCharacter() 中進行，用於下拉選單
    
    return {
        id: parseInt(cardId),
        name: cardData.Name,
        description: cardData.Description,
        characterId: cardData.CharactersId,
        characterName: CHARACTER_NAMES[cardData.CharactersId] || '未知',
        rarity: cardData.Rarity
    };
}

// 稀有度映射
const RARITY_NAMES = {
    3: 'R',
    4: 'SR',
    5: 'UR',
    7: 'LR',
    8: 'DR',
    9: 'BR'
};

// 格式化卡片顯示名稱
function formatCardName(card) {
    const rarityName = RARITY_NAMES[card.rarity] || `★${card.rarity}`;
    return `[${rarityName}] ${card.name}`;
}
