#!/usr/bin/env python3
"""
拒絶理由通知生成モジュール - v2.1.3

構成対比表と進歩性判断結果から、審査官視点の拒絶理由通知書を自動生成する。

機能:
1. 構成対比表の分析
2. 新規性・進歩性の判断（Claude Sonnet 4.5使用）
3. 拒絶理由通知書の生成（特許庁様式準拠）
4. 詳細な分析文書の生成
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import anthropic
from anthropic import AnthropicVertex


class RejectionNoticeGenerator:
    """拒絶理由通知生成クラス"""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-east5",
        model_name: Optional[str] = None
    ):
        """
        初期化

        Args:
            project_id: Google Cloud プロジェクトID（環境変数から取得可能）
            location: Vertex AIのロケーション
            model_name: Claudeモデル名（環境変数から取得可能）
        """
        # 環境変数から設定を取得
        self.project_id = project_id or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
        self.model_name = model_name or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5@20250929")

        if not self.project_id:
            raise ValueError("ANTHROPIC_VERTEX_PROJECT_ID環境変数が設定されていません")

        # Anthropic Vertex AIクライアントの初期化
        self.client = AnthropicVertex(
            project_id=self.project_id,
            region=location
        )

        # プロンプトテンプレートの読み込み
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """プロンプトテンプレートの読み込み"""
        template_path = Path(__file__).parent.parent / "docs" / "prompts" / "rejection_notice_prompt.md"

        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # メインプロンプト部分を抽出
                if "## メインプロンプト" in content:
                    parts = content.split("## メインプロンプト")
                    if len(parts) > 1:
                        return parts[1].split("---")[0].strip()
                return content
        else:
            # デフォルトのプロンプト
            return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """デフォルトのプロンプトテンプレート"""
        return """
あなたは日本特許庁の審査官です。構成対比表を分析し、新規性・進歩性を判断して拒絶理由通知書を作成してください。

審査基準に従い、客観的・論理的に判断し、以下の形式でJSON出力してください。
"""

    def generate_rejection_notice(
        self,
        comparison_table_path: str,
        assessment_summary_path: str,
        base_structure_path: str,
        output_dir: str
    ) -> Dict[str, str]:
        """
        拒絶理由通知を生成

        Args:
            comparison_table_path: 構成対比表（Markdown）のパス
            assessment_summary_path: 進歩性判断サマリーのパス
            base_structure_path: 本願特許の構成要素JSONパス
            output_dir: 出力ディレクトリ

        Returns:
            生成されたファイルのパス辞書
        """
        print(f"\n{'='*80}")
        print(f"拒絶理由通知書の生成を開始")
        print(f"{'='*80}\n")

        # 1. データ読み込み
        print("Step 1: データ読み込み中...")
        comparison_table = self._load_comparison_table(comparison_table_path)
        assessment_summary = self._load_assessment_summary(assessment_summary_path)
        base_structure = self._load_base_structure(base_structure_path)

        base_patent_id = base_structure.get('本願特許', {}).get('公開番号', 'Unknown')
        base_patent_title = base_structure.get('本願特許', {}).get('発明の名称', 'Unknown')

        print(f"  ✓ 本願特許: {base_patent_id}")
        print(f"  ✓ 発明の名称: {base_patent_title}")

        # 2. 構成対比表をJSON形式に変換
        print("\nStep 2: 構成対比表を分析中...")
        structured_data = self._structure_comparison_data(
            comparison_table,
            assessment_summary,
            base_structure
        )
        print(f"  ✓ 構成要素数: {len(structured_data['elements'])}個")

        # 3. Claude APIで分析・生成
        print("\nStep 3: Claude Sonnet 4.5で拒絶理由を分析中...")
        prompt = self._build_prompt(
            structured_data,
            base_patent_id,
            base_patent_title
        )

        result = self._call_claude_api(prompt)
        print(f"  ✓ 分析完了")

        # 4. 結果をファイルに出力
        print("\nStep 4: ファイルを出力中...")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_files = self._save_results(
            result,
            output_dir,
            base_patent_id
        )

        for file_type, file_path in output_files.items():
            print(f"  ✓ {file_type}: {file_path}")

        print(f"\n{'='*80}")
        print(f"✅ 拒絶理由通知書の生成完了")
        print(f"{'='*80}\n")

        return output_files

    def _load_comparison_table(self, table_path: str) -> str:
        """構成対比表（Markdown）の読み込み"""
        with open(table_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_assessment_summary(self, summary_path: str) -> Dict:
        """進歩性判断サマリーの読み込み"""
        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_base_structure(self, structure_path: str) -> Dict:
        """本願特許の構成要素の読み込み"""
        with open(structure_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _structure_comparison_data(
        self,
        comparison_table: str,
        assessment_summary: Dict,
        base_structure: Dict
    ) -> Dict:
        """
        構成対比表を構造化データに変換

        Args:
            comparison_table: Markdown形式の構成対比表
            assessment_summary: 進歩性判断サマリー
            base_structure: 本願特許の構成要素

        Returns:
            構造化された対比データ
        """
        # Markdown表をパースして構造化
        elements = []

        for element in base_structure.get('構成要件', []):
            element_data = {
                'element_id': element['構成要素番号'],
                'element_description': element.get('構成要素の簡単説明', element['構成要素']),
                'is_independent': element.get('is_independent', False),
                'full_text': element['構成要素']
            }
            elements.append(element_data)

        # X文献・Y文献の情報を追加
        x_refs = assessment_summary.get('x_references', {})
        y_refs = assessment_summary.get('y_references', {})

        structured_data = {
            'elements': elements,
            'x_references': x_refs.get('patents', []),
            'y_references': {
                'primary': y_refs.get('combinations', [{}])[0].get('primary_reference') if y_refs.get('combinations') else None,
                'secondary': y_refs.get('combinations', [{}])[0].get('secondary_references', []) if y_refs.get('combinations') else []
            },
            'comparison_table_markdown': comparison_table
        }

        return structured_data

    def _build_prompt(
        self,
        structured_data: Dict,
        base_patent_id: str,
        base_patent_title: str
    ) -> str:
        """
        Claude API用のプロンプトを構築

        Args:
            structured_data: 構造化された対比データ
            base_patent_id: 本願特許ID
            base_patent_title: 発明の名称

        Returns:
            完成したプロンプト
        """
        # 独立請求項の要素数をカウント
        independent_count = sum(1 for e in structured_data['elements'] if e['is_independent'])

        # X文献・Y文献のリストを作成
        x_refs_list = "\n".join([f"- {ref}" for ref in structured_data['x_references']])

        y_primary = structured_data['y_references']['primary'] or "なし"
        y_secondary = ", ".join(structured_data['y_references']['secondary']) or "なし"

        prompt = f"""# 拒絶理由通知書の作成

以下の構成対比表に基づき、本願発明の新規性・進歩性を審査し、拒絶理由通知書を作成してください。

## 本願特許情報
- 出願番号: {base_patent_id}
- 発明の名称: {base_patent_title}
- 独立請求項の構成要素数: {independent_count}個

## 構成対比表
{structured_data['comparison_table_markdown']}

## 引用文献
### X文献（単独文献）
{x_refs_list if x_refs_list else "なし"}

### Y文献（組み合わせ文献）
- 主引用発明: {y_primary}
- 副引用発明: {y_secondary}

---

## 指示

日本特許庁の審査基準に従い、以下を作成してください：

1. **新規性の判断**（X文献がある場合）
   - 全要素が単独文献で開示されているか確認
   - 判断結果と根拠を記載

2. **進歩性の判断**（Y文献がある場合）
   - 主引用発明との一致点・相違点を認定
   - 相違点の容易想到性を論理付け
   - 動機付けと阻害要因を検討

3. **拒絶理由通知書**
   - 特許庁の様式に従った正式な通知書
   - 適用条文の明示
   - 引用文献の正確な引用
   - 論理的で明確な説明

4. **分析文書**
   - 詳細な対比分析
   - 統計情報
   - 出願人への助言

---

## 出力形式

以下のJSON形式で出力してください：

```json
{{
  "analysis_document": {{
    "novelty_judgment": {{
      "result": "あり" | "なし",
      "reasoning": "...",
      "cited_references": [...]
    }},
    "inventive_step_judgment": {{
      "result": "あり" | "なし",
      "primary_reference": "...",
      "secondary_references": [...],
      "matching_points": [...],
      "differences": [...],
      "motivation": "...",
      "unexpected_effects": "..."
    }},
    "overall_assessment": "...",
    "advice": "..."
  }},
  "rejection_notice": {{
    "application_number": "{base_patent_id}",
    "invention_title": "{base_patent_title}",
    "applicable_provisions": [...],
    "reason_1_novelty": "...",
    "reason_2_inventive_step": "...",
    "cited_references": [...]
  }},
  "markdown_analysis": "...",
  "markdown_rejection_notice": "..."
}}
```

重要な原則:
- 客観的事実に基づく判断
- 審査基準の厳格な適用
- 引用文献の正確な引用
- 出願人への配慮
- 法的根拠の明示
"""

        return prompt

    def _call_claude_api(self, prompt: str) -> Dict:
        """
        Claude API を呼び出し

        Args:
            prompt: 送信するプロンプト

        Returns:
            Claude APIからのレスポンス（JSON）
        """
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=16000,
                temperature=0.0,  # 決定論的な判断
                system="""あなたは日本特許庁の審査官です。特許法および審査基準に精通しており、客観的・中立的な立場で特許出願の新規性・進歩性を判断します。

審査基準に厳格に従い、論理的で明確な拒絶理由通知書を作成してください。""",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # レスポンスからテキストを抽出
            response_text = response.content[0].text

            # JSONとして解析を試みる
            try:
                # コードブロックがある場合は除去
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response_text

                result = json.loads(json_str)
                return result
            except json.JSONDecodeError as e:
                print(f"警告: JSON解析エラー: {e}")
                # JSON解析失敗時は、テキストをそのまま格納
                return {
                    "raw_response": response_text,
                    "error": "JSON解析に失敗しました"
                }

        except Exception as e:
            print(f"エラー: Claude API呼び出しに失敗: {e}")
            raise

    def _save_results(
        self,
        result: Dict,
        output_dir: Path,
        base_patent_id: str
    ) -> Dict[str, str]:
        """
        結果をファイルに保存

        Args:
            result: Claude APIからの結果
            output_dir: 出力ディレクトリ
            base_patent_id: 本願特許ID

        Returns:
            保存したファイルのパス辞書
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{base_patent_id}_{timestamp}"

        output_files = {}

        # 1. JSON形式で完全な結果を保存
        json_path = output_dir / f"rejection_notice_{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        output_files['JSON'] = str(json_path)

        # 2. 分析文書（Markdown）を保存
        if 'markdown_analysis' in result:
            analysis_path = output_dir / f"analysis_{base_name}.md"
            with open(analysis_path, 'w', encoding='utf-8') as f:
                f.write(result['markdown_analysis'])
            output_files['分析文書'] = str(analysis_path)

        # 3. 拒絶理由通知書（Markdown）を保存
        if 'markdown_rejection_notice' in result:
            notice_path = output_dir / f"rejection_notice_{base_name}.md"
            with open(notice_path, 'w', encoding='utf-8') as f:
                f.write(result['markdown_rejection_notice'])
            output_files['拒絶理由通知書'] = str(notice_path)

        # 4. raw_responseがある場合（JSON解析失敗時）
        if 'raw_response' in result:
            raw_path = output_dir / f"rejection_notice_raw_{base_name}.txt"
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(result['raw_response'])
            output_files['Raw Response'] = str(raw_path)

        return output_files


if __name__ == "__main__":
    # テスト実行
    import sys

    if len(sys.argv) < 4:
        print("使用方法: python rejection_notice_generator.py <comparison_table_md> <assessment_summary_json> <structure_json> [output_dir]")
        sys.exit(1)

    comparison_table_path = sys.argv[1]
    assessment_summary_path = sys.argv[2]
    structure_path = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else "./rejection_notices"

    generator = RejectionNoticeGenerator()
    result = generator.generate_rejection_notice(
        comparison_table_path=comparison_table_path,
        assessment_summary_path=assessment_summary_path,
        base_structure_path=structure_path,
        output_dir=output_dir
    )

    print(f"\n✅ 拒絶理由通知書を生成しました")
    for file_type, file_path in result.items():
        print(f"  - {file_type}: {file_path}")
