import json
import os
import re
import sys
from rdkit import Chem

# 法律JSONのロード
LAW_SOURCES = [
    ("laws/law1.json", "麻薬及び向精神薬取締法"),
    ("laws/law2.json", "覚醒剤取締法"),
    ("laws/law3.json", "毒物及び劇物取締法")
    # ("data/laws/覚醒剤取締法.json", "覚醒剤取締法"),
]




def load_and_merge_laws():
    # 構造: { "SMILES": { "law": "...", "name": "...", "scope": [...], "description": "..." } }

    merged_laws = {}

    for filepath, law_name in LAW_SOURCES:
        if not os.path.exists(filepath):
            print(f"[Warning] {filepath} が見つかりません。")
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 辞書をマージする
        for pattern, info in data.items():
            new_info = info.copy()
            new_info["law"] = law_name # 新しい辞書にタグ付けする
            
            # まだ登録されていないSMILESならリストを作成
            if pattern not in merged_laws:
                merged_laws[pattern] = []
            
            # リストに追加（これで複数の法律が重なってもOK）
            merged_laws[pattern].append(new_info)

    return merged_laws

REGULATION_DB = load_and_merge_laws()

print(REGULATION_DB)



#SMILESを受け取り、規制リストにヒットしたものを詳細情報付きで返す
class check_regulations:
    def __init__(self, regulation_db):
        self.patterns = []

        for smiles_pattern, reg_list in regulation_db.items():
            mol = Chem.MolFromSmiles(smiles_pattern)
            if mol:
                for info in reg_list:
                    self.patterns.append({
                        "smiles": smiles_pattern,  # 結果表示用
                        "mol": mol,                # 検索用オブジェクト
                        "info": info               # 法律情報
                    })
            else:
                if reg_list:
                    name_ref = reg_list[0].get('name', 'Unknown')
                else:
                    name_ref = 'Unknown'
                print(f"[Warning] DB登録エラー: '{name_ref}' のSMILESが不正です。スキップします。", file=sys.stderr)


        # 化合物側鎖判定用 (ダミー原子形: *)
        inorganic_sidechains = [
            "CC(=O)*",      # アセチル基 (酢酸エステル等)
            "[CH1](=O)*",   # ホルミル基 (ギ酸エステル等)
            "OC(=O)*",      # 炭酸エステル系
            "N#C*",         # シアノ基
            "S=C=S"         # 二硫化炭素 (これはそのまま)
        ]
        self.inorganic_sidechain_patterns = [Chem.MolFromSmarts(s) for s in inorganic_sidechains]


        # 塩判定用
        inorganic_exceptions = [
            "CC(=O)[O-,OH]",      # 酢酸塩 (Acetate)
            "[CH1](=O)[O-,OH]",   # ギ酸塩 (Formate)
            "C(=O)([O-,OH])[O-,OH]", # 炭酸塩 (Carbonate)
            "C#N", "[C-]#[N+]",   # シアン (Cyanide)
            "S=C=S"               # 二硫化炭素
        ]
        self.inorganic_salt_patterns = [Chem.MolFromSmarts(s) for s in inorganic_exceptions]




    # 化合物の場合の有機・無機チェック
    def _analyze_compound_type(self, whole_mol, core_mol):
        # コア構造を除去して「側鎖(Side Chains)」だけを取り出す
        side_chains_mol = Chem.ReplaceCore(whole_mol, core_mol) # ReplaceCoreは、除去した部分にダミー原子(*)を残して側鎖を返す

        if side_chains_mol is None:
            return None

        # 鎖を個別のフラグメントに分解
        fragments = Chem.GetMolFrags(side_chains_mol, asMols=True)

        is_organic = False

        for frag in fragments:
            # ダミー原子(*)以外の原子で、炭素(C)があるか探す
            c_count = 0
            atoms = frag.GetAtoms()
            for atom in atoms:
                # 原子番号0はダミー原子なので無視
                if atom.GetAtomicNum() != 0 and atom.GetSymbol() == 'C':
                    c_count += 1

            if c_count > 0:
                # 炭素がある場合 -> 基本的に有機 + 例外チェック
                is_exception = False
                # 炭素数が3以上なら、複雑なので「有機」
                if c_count > 2:
                    is_organic = True
                    break

                # 炭素数が少ない場合、例外パターンにマッチするか確認
                for pat in self.inorganic_sidechain_patterns:
                    if frag.HasSubstructMatch(pat):
                        # マッチしたが、原子数がパターンとほぼ同じか確認(余計な有機鎖がないか)
                        # (*の分を含めて計算する必要があるため、少し緩めに判定(+1 or +2))
                        if frag.GetNumAtoms() <= pat.GetNumAtoms() + 1:
                            is_exception = True
                            break

                if not is_exception:
                    is_organic = True
                    break # 一つでも有機基があれば、全体として「有機化合物」

        if is_organic:
            return "有機化合物"
        else:
            return "無機化合物" # 炭素がない(Cl, S, Pのみ)、または例外無機炭素のみ




    # 塩類の場合の有機・無機チェック用
    def _classify_salt_type(self, frag):
        # 炭素(C)の有無チェック
        has_carbon = False
        c_count = 0
        for atom in frag.GetAtoms():
            if atom.GetSymbol() == 'C':
                has_carbon = True
                c_count += 1
        
        # 炭素なし -> 無機
        if not has_carbon:
            return "無機塩類"
        # 炭素あり -> 例外判定
        # Cが3個以上なら、複雑、「有機」
        if c_count > 2:
            return "有機塩類"
        # Cが1~2個の場合、例外パターン(酢酸・ギ酸・シアン等)にマッチするか確認
        for pat in self.inorganic_salt_patterns:
            if frag.HasSubstructMatch(pat):
                if frag.GetNumAtoms() <= pat.GetNumAtoms() + 1: # 構造がほぼ一致するか
                    return "無機塩類"

        return "有機塩類"




    def check(self, target_smiles):
        # 入力チェック
        target_mol = Chem.MolFromSmiles(target_smiles)
        if target_mol is None:
            print(f"[Error] 入力されたSMILES '{target_smiles}' は解析できませんでした。")
            return [] 

        # 前処理
        try:
            fragments = Chem.GetMolFrags(target_mol, asMols=True, sanitizeFrags=True)
        except Exception:
            fragments = [target_mol]

        
        # 水和物判定用
        water_patterns = {"O", "[OH2]", "[OH2+]", "[OH3+]"}

        found_regulations = []

        # 全フラグメント総当たりチェック
        for i, main_frag in enumerate(fragments):

            # 塩類チェック
            other_frags = [f for j, f in enumerate(fragments) if j != i]
            env_has_hydrate = False
            detected_salt_types = set()

            for other in other_frags:
                smi = Chem.MolToSmiles(other, isomericSmiles=True, canonical=True)
                # 水判定
                if smi in water_patterns:
                    env_has_hydrate = True
                    continue
                # 塩判定 (自分より小さいものを塩候補とする)
                if other.GetNumAtoms() < main_frag.GetNumAtoms():
                    salt_category = self._classify_salt_type(other)
                    detected_salt_types.add(salt_category)




            # DB照合
            for pattern_data in self.patterns:
                query_mol = pattern_data["mol"]     # 規制対象の構造
                info = pattern_data["info"]         # 法律情報
                db_smiles = pattern_data["smiles"]  # 登録SMILES文字列
                scope = info.get("scope", [])
                detected_type = None

                controlled_isomers = ("isomers" in scope) or ("specific_isomers" in scope) #["その異性体", "特定の異性体"]
                controlled_salts = ("salts" in scope) # ["及びその塩類"]
                controlled_hydrate = ("hydrates" in scope) # ["及びその水和物"]
                controlled_derivatives = ("esters" in scope) or ("ethers" in scope) # ["そのエステル", "そのエーテル"]
                controlled_compounds = ("compounds" in scope) or ("organic_compounds" in scope) or ("inorganic_compounds" in scope) # ["その化合物", "その有機塩類", その無機塩類]
                controlled_itself = ("itself" in scope) # ["それ"]

                annotation_text_except_itself = "です。(※法令上は化合物・塩類・水和物のみ規定の可能性あり)"
                annotation_text_analogues = "です。{規制物質(あるいはその異性体)の部分構造と一致} \n法令の該当箇所を確認してください。 \n(誤検知の可能性があります)"
            
                # RDKit 部分構造マッチ
                if main_frag.HasSubstructMatch(query_mol):
                
                    # A. 完全一致判定 (Isomeric SMILESで比較)(原子数が同じなら、余計なものがついていない -> そのものか異性体)
                    if main_frag.GetNumAtoms() == query_mol.GetNumAtoms():
                        try:
                            input_canon = Chem.MolToSmiles(main_frag, isomericSmiles=True)
                            query_canon = Chem.MolToSmiles(query_mol, isomericSmiles=True)
                        
                            if input_canon == query_canon:
                                base_name = "それ(完全一致)"
                            else:
                                base_name = "その異性体"

                            if controlled_itself or controlled_isomers:
                                detected_type = base_name
                            else:
                                # scopeに本体が含まれていないが、構造は完全に一致している(塩のみ規制などの場合)
                                # 後で塩チェックに引っかかれば上書きされるよう、仮置き
                                detected_type = f"{base_name} {annotation_text_except_itself}"
                        except:
                            detected_type = "それ(構造一致)"
                
                    # B. 部分一致 (誘導体・化合物)
                    else:
                        if controlled_derivatives:
                            detected_type = "その誘導体(エステル/エーテル等)"
                        elif controlled_compounds:
                            comp_type = self._analyze_compound_type(main_frag, query_mol)
                            if "organic_compounds" in scope and comp_type == "有機化合物":
                                detected_type = "その有機化合物"
                            elif "inorganic_compounds" in scope and comp_type == "無機化合物":
                                detected_type = "その無機化合物"
                            else:
                                # scopeで細分化されていない、またはscope外の場合
                                detected_type = f"その化合物({comp_type})"
                        else:
                            detected_type = f"構造にこれを含む物質 {annotation_text_analogues}"

                    # 塩・水和物の判定 (detected_typeに追記)
                    suffix = []
                    if env_has_hydrate:
                        if controlled_hydrate:
                            suffix.append("水和物")
                        elif controlled_salts: 
                            suffix.append("塩類(水和物)")
                        else:
                            suffix.append("水和物(※対象の可能性)")

                    if detected_salt_types:
                        for stype in detected_salt_types:
                            if "inorganic_salts" in scope and stype == "無機塩類":
                                suffix.append("無機塩類")
                            elif "organic_salts" in scope and stype == "有機塩類":
                                suffix.append("有機塩類")
                            elif "salts" in scope:
                                suffix.append("塩類")
                            elif "compounds" in scope:
                                suffix.append(f"化合物({stype})")
                            #else:
                            #    suffix.append("塩類(※規制対象外の可能性あり)")

                    # 塩類の場合の文字列結合
                    if suffix:
                        suffix_str = '/'.join(suffix)
                        if detected_type:
                            clean_name = detected_type.replace(annotation_text_except_itself, "").strip()
                            if annotation_text_analogues in clean_name:
                                detected_type = f"{clean_name} の{suffix_str}{annotation_text_analogues}"
                            else:
                                detected_type = f"{clean_name} の{suffix_str}"
                        else:
                            detected_type = f"その{suffix_str}"

                # 結果リストに追加
                if detected_type:
                    found_regulations.append({
                        "law": info["law"],
                        "name": info.get("name", "分類なし"),
                        "detected_type": detected_type,
                        "scope": scope,
                        "description": info.get("description", ""),
                       "pattern_matched": db_smiles
                    })

        return found_regulations




def print_report(results):
    if results:
        print("\n" + "-"*40)
        print(f"検索結果: {len(results)}件")
        print("【警告】 以下の法規制に該当する可能性があります！")
        for res in results:
            print(f"・法律名 : {res['law']}")
            print(f"・該当箇所: {res['name']}")
            print(f"・登録名 : {res['description']}")
            print(f"・該当範囲: {res['detected_type']}")
            print("-" * 30)
    else:
        print("\n" + "-"*40)
        print("法規制の対象となる特徴的な構造は見つかりませんでした。")
        print("-" * 40)



checker = check_regulations(REGULATION_DB)

def run_check_and_print(smiles):
    results = checker.check(smiles)
    print_report(results)