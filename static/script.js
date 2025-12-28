
function escapeHtml(str) {
    if(!str) return str;
    return str.replace(/[&<>"']/g, function(match) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[match];
    });
}




document.addEventListener('DOMContentLoaded', () => {
    const copyBtn = document.getElementById('copyBtn');
    const resultArea = document.getElementById('resultArea');

    if(copyBtn && resultArea) {
        copyBtn.addEventListener('click', () => {
            // テキストを取得 (HTMLタグを除去して文字だけ取得)
            const textToCopy = resultArea.innerText;

            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'コピーしました！';
                copyBtn.classList.add('copied');

                setTimeout(() => {
                    copyBtn.textContent = originalText;
                    copyBtn.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                alert('コピーに失敗しました');
            });
        });
    }
});




document.addEventListener('DOMContentLoaded', () => {
    const chemicalInput = document.getElementById('chemicalInput');

    // Safari対策のフラグ管理
    let isIME = false; 

    if (chemicalInput) {
        
        // 変換開始：フラグを立てる
        chemicalInput.addEventListener('compositionstart', () => {
            isIME = true;
        });

        // 変換終了：フラグを下ろす(が、時差)
        chemicalInput.addEventListener('compositionend', () => {
            isIME = true; // 念のためTrueのままにしておく
            // フラグを下ろす予約をする
            setTimeout(() => {
                isIME = false;
            }, 50);
        });

        // キー入力判定
        chemicalInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // 変換中（または変換直後のSafariのEnter）なら無視！
                if (isIME) {
                    e.preventDefault();
                    return;
                }

                // 完全に文字が確定している時だけ実行
                e.preventDefault();
                checkChemical();
            }
        });
    }
});




let latestRequestId = 0;

async function checkChemical() {
    const text = document.getElementById('chemicalInput').value;
    const resultArea = document.getElementById('resultArea');
    const inputVal = document.getElementById("chemicalInput").value;

    latestRequestId++;
    const myRequestId = latestRequestId;
    if(!text) return;

    if(copyBtn) copyBtn.style.display = 'none';


    const loadingMessages = [
        "データベースを検索中...",
        "サーバーを起動しています（少々時間がかかります）...",
        "構造式を解析中...",
        "もうすぐ結果が出ます..."
    ];

    resultArea.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p style="color:#666;" id="loading-msg">${loadingMessages[0]}</p>
        </div>
    `;

    let msgIndex = 0;
    const intervalId = setInterval(() => {
        msgIndex = (msgIndex + 1) % loadingMessages.length;
        const el = document.getElementById("loading-msg");
        if (el) {
            el.innerText = loadingMessages[msgIndex];
        }
    }, 4500);



    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        const data = await response.json();


        if (myRequestId !== latestRequestId) {
            console.log("古いリクエストの結果が遅れて届いたので、無視しました。");
            return;
        }


        if (data.error) {
            resultArea.innerHTML = `<p style="color:red">エラー: ${data.error}</p>`;
            return;
        }

        // 結果HTMLの生成
        let html = `<h3>${escapeHtml(inputVal)}</h3>`;
        html += `<p><strong>${escapeHtml(data.english_name)}</strong> <small>(独自の規則で翻訳されています。)</small></p>`;
        html += `<p><strong>SMILES:</strong> ${data.smiles || "変換できませんでした"}</p>`;
        
        // まずデータがあるか確認し、nullなら空配列 [] に置き換える
        const regulationsList = data.regulations || [];

        if (regulationsList.length === 0) {
            html += `<p style="color:green"><small> 規制情報は見つかりませんでした</small></p>`;
        } else {
            html += `<h4 style="color:red"> 検出された法規制 (${regulationsList.length}件)</h4>`;
            html += `<ul>`;
            
            regulationsList.forEach(reg => {
                html += `<li>
                    <strong>${reg.law}</strong> : ${reg.name}
                    <small>${reg.description} : ${reg.detected_type} </small>
                </li>`;
            });
            html += `</ul>`;
        }

        resultArea.innerHTML = html;

        // ★ここでボタンを表示する！
        if(copyBtn) copyBtn.style.display = 'block';

    } catch (err) {
        if (myRequestId === latestRequestId) {
            console.error(err);
            resultArea.innerHTML = `<p style="color:red; text-align:center;">通信エラーが発生しました。<br>もう一度お試しください。</p>`;
        }
    } finally {
        // 成功しても失敗しても、必ずここでタイマーを止める
        clearInterval(intervalId);
    }
}




// モーダル要素
const modalOverlay = document.getElementById('modalOverlay');
const modalTitle = document.getElementById('modalTitle');
const modalBody = document.getElementById('modalBody');
const closeBtn = document.getElementById('closeModalBtn');
// 各ボタン
const newsBtn = document.getElementById('newsBtn');
const supportLaw = document.getElementById('supportLawBtn');
const howToUseBtn = document.getElementById('howToUseBtn');

// モーダルを開く関数
function openModal(title, content, isHtml = false) {
    modalTitle.textContent = title;
    if (isHtml) {
        modalBody.innerHTML = content;
    } else {
        // テキストファイルの場合は改行コードを <br> に変換して表示
        modalBody.innerHTML = content.replace(/\n/g, '<br>');
    }
    
    modalOverlay.classList.add('active');
}

// モーダルを閉じる関数
function closeModal() {
    modalOverlay.classList.remove('active');
}

// 「使い方」ボタン
howToUseBtn.addEventListener('click', () => {
    const usageText = `
        <h3>化学物質 法規制チェッカー</h3>
        <hr>
        <h4>【操作方法】</h4>
        <ul>
            <li><strong>文字入力:</strong> 入力欄に目的の物質名を日本語命名法、IUPAC命名法、SMILESのいずれかで入力してください。(一部の一般名にも対応しています。)</li>
            <li><strong>確定:</strong> 「確定」ボタンを押すと入力した内容を規制する法令があるかを探します。(出力に時間がかかることがあります。)</li>
            <li> ※ 日本語で入力した場合、独自の規則で英語に変換された後に、smilesに変換する操作を行うため、うまく出力されない場合があります。</li>
            <li> ※ 現在、検出が可能な法令・物質については「対応している法令」を参照してください。</li>
        </ul>
    `;
    openModal('使い方', usageText, true);
});

// 「対応している法令」ボタン(外部ファイル読み込み)
supportLawBtn.addEventListener('click', () => {
    modalBody.textContent = '読み込み中...';
    openModal('対応している法令', '読み込み中...', false);

    fetch('/static/laws.txt')
        .then(response => {
            if (!response.ok) throw new Error('読み込み失敗');
            return response.text();
        })
        .then(text => {
            // 読み込めたら中身を書き換える
            modalBody.innerHTML = text.replace(/\n/g, '<br>');
        })
        .catch(err => {
            modalBody.textContent = '読み込みに失敗しました。';
        });
});

//「お知らせ」ボタン(外部ファイル読み込み)
newsBtn.addEventListener('click', () => {
    openModal('お知らせ', '読み込み中...', false);

    fetch('/static/news.txt')
        .then(response => response.text())
        .then(text => {
            modalBody.innerHTML = text.replace(/\n/g, '<br>');
        })
        .catch(err => {
            modalBody.textContent = '読み込みに失敗しました。';
        });
});

// 閉じる動作
// 「閉じる」ボタンを押した時
closeBtn.addEventListener('click', closeModal);
// 背景(オーバーレイ)をクリックした時
modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
        closeModal();
    }
});




document.addEventListener('DOMContentLoaded', () => {
    const pOverlay = document.getElementById('precautionsOverlay'); // 1枚目
    const dOverlay = document.getElementById('disclaimersOverlay'); // 2枚目

    // 2枚目
    const showDisclaimer = () => {
        if (!dOverlay) return;
        dOverlay.classList.add('fade-in');

        // 閉じる関数
        const closeDisclaimer = () => {
            dOverlay.classList.remove('fade-in');
        };

        // 30秒タイマー
        const dTimerId = setTimeout(closeDisclaimer, 30000);

        // クリックで閉じる
        dOverlay.addEventListener('click', () => {
            closeDisclaimer();
            clearTimeout(dTimerId);
        });
    };

    // 1枚目
    if (pOverlay) {
        const closePrecaution = () => {
            pOverlay.classList.add('fade-out');
            
            // アニメーションが終わる1秒後に次の画面を呼ぶ
            setTimeout(() => {
                showDisclaimer(); 
            }, 750); 
        };

        // 30秒タイマー
        const pTimerId = setTimeout(closePrecaution, 30000);

        // クリックで閉じる
        pOverlay.addEventListener('click', () => {
            closePrecaution();
            clearTimeout(pTimerId);
        });
    }
});
