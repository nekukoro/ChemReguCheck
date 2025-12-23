# 辞書を充実させる。

import json
import os
import re
import subprocess
import checker




# 表記揺れ対策の辞書
def load_synonyms():
    filepath = "dicts/synonyms_dict.json"
    if not os.path.exists(filepath):
        return {} # ファイルがなければ空の辞書を返す(エラーにしない)
        
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)




synonym_dict = load_synonyms()
 # シノニム辞書にある言葉が含まれていたら、扱える形に置換する
def normalize_text(text):
    sorted_keys = sorted(synonym_dict.keys(), key=len, reverse=True)
    for common_name in sorted_keys:
        formal_name = synonym_dict[common_name]
        text = text.replace(common_name, formal_name)
        
    return text




# 辞書統合
def load_and_merge_dictionaries():
    combined_dict = {}

    sources = [
        # (ファイルパス, 役割タグ, 辞書内キー)
        ("dicts/prefixes_dict.json",  "prefix",   "prefix"),
        ("dicts/modifiers_dict.json", "modifier", "modifier"),
        ("dicts/cores_dict.json",     "core",     "core"),
        ("dicts/suffixes_dict.json",  "suffix",   "suffix") 
    ]

    for filepath, role, trans_key in sources:
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} が見つかりません。スキップします。")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for japanese, english in data.items():

            if japanese not in combined_dict:
                combined_dict[japanese] = {
                    "translations": {},
                    "roles": []
                }
            # 情報を追加
            # 役割を追加
            combined_dict[japanese]["roles"].append(role)
            # 翻訳語を追加
            combined_dict[japanese]["translations"][trans_key] = english

    return combined_dict




translation_dict = load_and_merge_dictionaries()
# 入力分割
def tokenize_and_parse(text):
    tokens = []

    # 最長一致でトークン化する
    # 辞書のキーを「文字数が長い順」にソートする  これにより「ジメチル」があるときに「ジ」で切れてしまうのを防ぐ
    sorted_keys = sorted(translation_dict.keys(), key=len, reverse=True)

    # 正規表現パターンを作成: (フェノール|アセチル|モルヒネ|...)
    pattern = re.compile("|".join(map(re.escape, sorted_keys)))

    # 文字列を前からローラー
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if match:
            word = match.group(0)
            token_data = translation_dict[word]
            tokens.append({
                "original": word,
                "data": token_data
            })
            pos = match.end()
        else:
            # マッチしない文字があった場合(数字やハイフンなど)  「そのまま」英語として使う扱いにする(辞書にないから警告は付けたい)
            char = text[pos]
            tokens.append({"original": char, "data": {"type": "raw", "english": char}})
            pos += 1

    return tokens




# 結合
def translate_tokens_with_reorder(tokens):
    english_parts = []     # 本体(メチル、アンモニウムなど)
    delayed_suffixes = []  # 後ろに飛ばすやつ(塩化、酢酸など)

    for i, token in enumerate(tokens):
        # 辞書にない文字はそのまま追加
        if "data" not in token or "type" in token["data"]:
            english_parts.append(token["original"])
            continue

        token_info = token["data"]
        roles = token_info["roles"]
        translations = token_info["translations"]

        
        # 1. これは「後ろに飛ばすべき言葉（Suffix）」か？
        # 条件: roleにsuffixが含まれる AND 文末ではない(後ろに何かが続く＝塩やエステルである)
        if "suffix" in roles and i < len(tokens) - 1:
            # Suffix用の英語(chloride, acetateなど)をリストに確保して、本体には追加しない
            delayed_suffixes.append(translations["suffix"])
            continue

        # 2. 通常の単語の翻訳
        selected_english = ""
        is_last_word = (i == len(tokens) - 1)

        if is_last_word and "core" in translations:
            selected_english = translations["core"]
        elif "modifier" in translations:
            selected_english = translations["modifier"]
        elif "prefix" in translations:
            selected_english = translations["prefix"]
        else:
            # 万が一どれにも当てはまらない場合(たぶん無い)
            selected_english = list(translations.values())[0]

        english_parts.append(selected_english)

    if not english_parts and delayed_suffixes:
        pass 
    
    result_list = english_parts + delayed_suffixes
    
    return " ".join(result_list)




# SMILES化
def convert_name_to_smiles(english_name):

    jar_path = "libs/opsin-cli-2.8.0-jar-with-dependencies.jar"

    if not os.path.exists(jar_path):
        print(f"エラー: {jar_path} が見つかりません。")
        print("libsフォルダの中に opsin-cli.jar はあるか？")
        return None

    # コマンドの準備 (標準入力待ち受けモード)
    command = ["java", "-jar", jar_path, "-osmi"]

    try:
        result = subprocess.run(
            command,
            input=english_name,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        # 成功判定
        if result.returncode == 0:
            smiles = result.stdout.strip()
            if smiles:
                return smiles
            else:
                return None
        else:
            # エラー時
            print(f"OPSIN変換エラー: {result.stderr.strip()}")
            return None

    except Exception as e:
        print(f"予期せぬエラー: {e}")
        return None




# --- テスト実行 ---


if __name__ == "__main__":
    input_text = "ヘロイン"

    normalized_text = normalize_text(input_text)  # 正規化(normalize)

    tokens = tokenize_and_parse(normalized_text)  # トークン化

    english_name = translate_tokens_with_reorder(tokens)  # 並べ替え+英語に変換+結合

    smiles = convert_name_to_smiles(english_name)  # SMILESに変換

    print(f"入力: {input_text}")
    print(f"正規化後: {normalized_text}")
    print(f"英語名: {english_name}") 
    print(f"出力(SMILES): {smiles}")

    checker.run_check_and_print(smiles)