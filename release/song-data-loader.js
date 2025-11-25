// 歌曲數據加載器
// 從 Musics.yaml 加載並處理歌曲數據

// 全局變量存儲歌曲數據
let songDatabase = null;

// 加載歌曲數據
async function loadSongDatabase() {
    try {
        // 嘗試多個可能的路徑
        const possiblePaths = [
            '../Data/Musics.yaml',  // 從 web/ 訪問
            'Data/Musics.yaml',     // 從根目錄訪問
            './Data/Musics.yaml'    // 相對路徑
        ];

        let response = null;
        let lastError = null;

        for (const path of possiblePaths) {
            try {
                response = await fetch(path);
                if (response.ok) {
                    console.log(`成功從 ${path} 載入歌曲數據`);
                    break;
                }
            } catch (err) {
                lastError = err;
                console.warn(`嘗試載入 ${path} 失敗:`, err.message);
            }
        }

        if (!response || !response.ok) {
            throw lastError || new Error('無法從任何路徑載入歌曲數據');
        }

        const yamlText = await response.text();
        const musicsList = jsyaml.load(yamlText);

        // 轉換為以 ID 為鍵的對象格式
        songDatabase = {};
        if (Array.isArray(musicsList)) {
            musicsList.forEach(music => {
                if (music.Id) {
                    songDatabase[music.Id] = music;
                }
            });
        }

        console.log('歌曲數據加載成功，共載入', Object.keys(songDatabase).length, '首歌曲');
        return true;
    } catch (error) {
        console.error('加載歌曲數據失敗:', error);
        return false;
    }
}

// 難度映射
const DIFFICULTY_NAMES = {
    '01': 'Easy',
    '02': 'Normal',
    '03': 'Hard',
    '04': 'Expert',
    '05': 'Master',
    '06': 'Master+'
};

// 獲取歌曲列表
function getSongList() {
    if (!songDatabase) return [];

    const songs = [];
    for (const [musicId, musicData] of Object.entries(songDatabase)) {
        // 跳過無效歌曲
        if (!musicData.Title || musicData.Title === '？？？') {
            continue;
        }

        songs.push({
            id: musicId,
            name: musicData.Title
        });
    }

    // 按 OrderId 排序（如果有），否則按 ID 排序
    return songs.sort((a, b) => {
        const aOrder = songDatabase[a.id].OrderId || parseInt(a.id);
        const bOrder = songDatabase[b.id].OrderId || parseInt(b.id);
        return aOrder - bOrder;
    });
}

// 根據歌曲 ID 獲取歌曲信息
function getSongById(musicId) {
    if (!songDatabase || !songDatabase[musicId]) {
        return null;
    }

    const musicData = songDatabase[musicId];
    return {
        id: musicId,
        name: musicData.Title
    };
}

// 格式化歌曲顯示名稱
function formatSongName(song) {
    return `${song.name} (${song.id})`;
}
