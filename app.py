from flask import Flask, render_template, request, jsonify
import ja_to_smiles  # 名前を変えたメインロジックを読み込む
import checker       # 法規制チェッカー

app = Flask(__name__)

# --- サーバー起動時に1回だけDBを準備 ---
print("システム起動中: 辞書をロードしています...")
# jp_smiles_py側の辞書ロード (※必要なら関数を公開して呼ぶ形に修正)
# ここでは簡単のため、モジュール読み込み時点でロードされているものを使います

# checker側のDBロード
REGULATION_DB = checker.load_and_merge_laws()
main_checker = checker.check_regulations(REGULATION_DB)
print("ロード完了！")


# 1. トップページを表示する機能
@app.route('/')
def index():
    return render_template('index.html')


# 2. 検索リクエストを受け取る機能 (API)
@app.route('/api/search', methods=['POST'])
def search_api():
    print("\n--- 【デバッグ】検索リクエスト受信 ---")
    
    # ブラウザから送られてきたデータを取り出す
    data = request.json
    input_text = data.get('text', '')
    print(f"1. 受信したテキスト: {input_text}")

    if not input_text:
        return jsonify({"error": "文字を入力してください"}), 400

    try:
        # A. 日本語 -> 英語 -> SMILES
        normalized = ja_to_smiles.normalize_text(input_text)
        tokens = ja_to_smiles.tokenize_and_parse(normalized)
        english_name = ja_to_smiles.translate_tokens_with_reorder(tokens)
        smiles = ja_to_smiles.convert_name_to_smiles(english_name)
        
        print(f"2. 変換された英語名: {english_name}")
        print(f"3. 変換されたSMILES: {smiles}")

        if not smiles:
            print("!! SMILES変換失敗")
            return jsonify({
                "english_name": english_name,
                "smiles": None,
                "regulations": [],
                "message": "SMILES変換に失敗しました"
            })

        # B. 法規制チェック
        # ★ここでチェッカーの中にデータが入っているか確認
        print(f"4. チェッカーの登録パターン数: {len(main_checker.patterns)}")
        
        check_results = main_checker.check(smiles)
        print(f"5. 法規制チェック結果: {len(check_results)} 件ヒット")
        
        # 中身も見てみる
        for res in check_results:
            print(f"   - {res['law']}: {res['detected_type']}")

        # C. 結果をJSONで返す
        return jsonify({
            "original": input_text,
            "english_name": english_name,
            "smiles": smiles,
            "regulations": check_results
        })

    except Exception as e:
        print(f"!! エラー発生: {e}")
        import traceback
        traceback.print_exc() # 詳細なエラー場所を表示
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, port=5000)