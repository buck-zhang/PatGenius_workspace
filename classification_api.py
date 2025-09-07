#!/usr/bin/env python3
"""
独立した特許分類検索API
OpenSearchに依存しない分類検索システムのAPI層
"""

from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
from classification_search_engine import ClassificationDatabase

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション初期化
app = FastAPI(
    title="独立特許分類検索API",
    description="OpenSearchに依存しない独立した特許分類検索システム",
    version="1.0.0"
)

# CORSミドルウェア追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 分類データベースをグローバルで初期化
classification_db = None

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時に分類データベースを初期化"""
    global classification_db
    logger.info("分類データベースを初期化中...")
    
    classification_db = ClassificationDatabase()
    classification_db.load_data()
    
    stats = classification_db.get_statistics()
    logger.info(f"分類データベース初期化完了: {stats['total_classifications']:,} 件")

# APIモデル定義
class KeywordSearchRequest(BaseModel):
    keyword: str = Field(..., description="検索キーワード", example="画像形成装置")
    systems: List[str] = Field(default=["IPC", "FI", "CPC"], description="対象の分類システム")
    limit: int = Field(default=20, description="結果数制限")
    highlight: bool = Field(default=True, description="キーワードハイライト表示")

class HierarchyItem(BaseModel):
    code: str
    title_ja: str
    title_en: str
    level: int
    num_documents: Optional[int] = None

class ClassificationInfo(BaseModel):
    classification_system: str
    code: str
    title_ja: str
    title_en: str
    level: int
    num_documents: int
    theme: Optional[str] = None
    concordance: Optional[str] = None
    keywords_ja: Optional[str] = None
    keywords_en: Optional[str] = None
    # 階層情報を追加
    parent_classifications: Optional[List[HierarchyItem]] = None
    child_classifications: Optional[List[HierarchyItem]] = None
    hierarchy_path: Optional[List[HierarchyItem]] = None
    total_children: Optional[int] = None
    total_parents: Optional[int] = None
    # ハイライト情報
    title_ja_highlighted: Optional[str] = None
    title_en_highlighted: Optional[str] = None
    # マッチスコア
    match_score: Optional[float] = None

class KeywordSearchResponse(BaseModel):
    total: int
    results: List[ClassificationInfo]
    query_info: Dict[str, Any]

class HierarchyInfo(BaseModel):
    current: Optional[ClassificationInfo]
    parents: List[ClassificationInfo]
    children: List[ClassificationInfo]

# API エンドポイント
@app.get("/health", tags=["System"])
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "database_loaded": classification_db is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats", tags=["System"])
async def get_statistics():
    """データベース統計情報"""
    if not classification_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    stats = classification_db.get_statistics()
    return stats

@app.post("/search/keyword", response_model=KeywordSearchResponse, tags=["Search"])
async def keyword_search(request: KeywordSearchRequest):
    """
    キーワードから分類コード検索
    技術用語を入力すると関連する分類コードをアウトプット
    """
    if not classification_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    start_time = datetime.now()
    
    try:
        results = classification_db.search_by_keyword(
            keyword=request.keyword,
            systems=request.systems,
            limit=request.limit,
            highlight=request.highlight
        )
        
        end_time = datetime.now()
        
        # 結果をAPIモデルに変換
        classification_results = []
        for result in results:
            # 階層情報をHierarchyItemに変換
            result_copy = result.copy()
            
            if 'parent_classifications' in result_copy:
                result_copy['parent_classifications'] = [
                    HierarchyItem(**item) for item in result_copy['parent_classifications']
                ]
            
            if 'child_classifications' in result_copy:
                result_copy['child_classifications'] = [
                    HierarchyItem(**item) for item in result_copy['child_classifications']
                ]
            
            if 'hierarchy_path' in result_copy:
                result_copy['hierarchy_path'] = [
                    HierarchyItem(**item) for item in result_copy['hierarchy_path']
                ]
            
            classification_results.append(ClassificationInfo(**result_copy))
        
        return KeywordSearchResponse(
            total=len(results),
            results=classification_results,
            query_info={
                "keyword": request.keyword,
                "systems": request.systems,
                "limit": request.limit,
                "execution_time_ms": int((end_time - start_time).total_seconds() * 1000)
            }
        )
        
    except Exception as e:
        logger.error(f"Keyword search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/classification/{system}/{code:path}", response_model=ClassificationInfo, tags=["Search"])
async def get_classification_details(
    system: str = Path(..., description="分類システム", regex="^(IPC|FI|CPC)$"),
    code: str = Path(..., description="分類コード", example="A01D34/13")
):
    """
    分類コードから詳細情報取得
    分類コードを入力するとその説明をアウトプット
    """
    if not classification_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        logger.info(f"Looking for classification: {system}_{code}")
        result = classification_db.get_classification_info(code, system)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Classification {system}_{code} not found")
        
        # 階層情報も含めて返す
        hierarchy_info = classification_db._get_hierarchy_info_for_classification(f"{system}_{code}")
        result.update(hierarchy_info)
        
        return ClassificationInfo(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification details error: {e}")
        raise HTTPException(status_code=500, detail=f"Details error: {str(e)}")

@app.get("/hierarchy/{system}/{code:path}", response_model=HierarchyInfo, tags=["Search"])
async def get_hierarchical_info(
    system: str = Path(..., description="分類システム", regex="^(IPC|FI|CPC)$"),
    code: str = Path(..., description="分類コード", example="A01D"),
    include_parents: bool = Query(True, description="上位分類も含める"),
    include_children: bool = Query(True, description="下位分類も含める")
):
    """
    上位・下位概念を考慮した階層検索
    分類コードの上位下位概念を含む階層構造をアウトプット
    """
    if not classification_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        result = classification_db.get_hierarchical_info(
            code=code,
            system=system,
            include_parents=include_parents,
            include_children=include_children
        )
        
        # 結果を変換
        hierarchy_result = HierarchyInfo(
            current=ClassificationInfo(**result['current']) if result['current'] else None,
            parents=[ClassificationInfo(**p) for p in result['parents']],
            children=[ClassificationInfo(**c) for c in result['children']]
        )
        
        return hierarchy_result
        
    except Exception as e:
        logger.error(f"Hierarchical search error: {e}")
        raise HTTPException(status_code=500, detail=f"Hierarchy error: {str(e)}")

@app.get("/search/suggest", tags=["Search"])
async def get_search_suggestions(
    q: str = Query(..., description="検索キーワード", example="画像"),
    limit: int = Query(5, description="サジェスト数")
):
    """検索キーワードサジェスト"""
    if not classification_db:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        # 簡易的なサジェスト実装
        results = classification_db.search_by_keyword(q, limit=limit)
        
        suggestions = []
        seen_keywords = set()
        
        for result in results:
            # タイトルからキーワードを抽出
            title = result.get('title_ja', '') or result.get('title_en', '')
            if title and title not in seen_keywords:
                suggestions.append({
                    'keyword': title[:20] + ('...' if len(title) > 20 else ''),
                    'system': result['classification_system'],
                    'code': result['code']
                })
                seen_keywords.add(title)
                
                if len(suggestions) >= limit:
                    break
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Suggestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Suggestion error: {str(e)}")

# 静的ファイルサーブ用（UI用）
@app.get("/ui", response_class=HTMLResponse, tags=["UI"])
async def serve_ui():
    """簡易検索UI"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>独立特許分類検索システム</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            .container {
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            h1 {
                text-align: center;
                color: #4a5568;
                margin-bottom: 30px;
                font-size: 2.5em;
            }
            .search-section {
                background: #f7fafc;
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 25px;
                border: 2px solid #e2e8f0;
            }
            .search-input {
                width: 100%;
                padding: 15px;
                border: 2px solid #cbd5e0;
                border-radius: 8px;
                font-size: 16px;
                margin-bottom: 15px;
                transition: border-color 0.3s;
            }
            .search-input:focus {
                outline: none;
                border-color: #4299e1;
                box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
            }
            .search-btn {
                background: linear-gradient(135deg, #4299e1, #3182ce);
                color: white;
                border: none;
                padding: 15px 25px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
                margin-right: 10px;
                margin-bottom: 10px;
                transition: transform 0.2s;
            }
            .search-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(66, 153, 225, 0.4);
            }
            .example-btn {
                background: #e2e8f0;
                color: #4a5568;
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                margin: 5px;
                transition: background-color 0.2s;
            }
            .example-btn:hover {
                background: #cbd5e0;
            }
            .results-section {
                display: none;
                margin-top: 25px;
            }
            .results-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding: 15px;
                background: #edf2f7;
                border-radius: 8px;
            }
            .result-item {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
                background: white;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .result-item:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .system-badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                color: white;
                margin-right: 10px;
            }
            .system-ipc { background: #4299e1; }
            .system-fi { background: #48bb78; }
            .system-cpc { background: #ed8936; }
            .code {
                font-family: 'Courier New', monospace;
                background: #f7fafc;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: bold;
            }
            .title-ja {
                font-weight: bold;
                color: #2d3748;
                margin: 10px 0 5px 0;
            }
            .title-en {
                color: #718096;
                font-style: italic;
                font-size: 14px;
            }
            .loading {
                text-align: center;
                padding: 40px;
                font-size: 18px;
                color: #718096;
            }
            .error-message {
                background: #fed7d7;
                color: #c53030;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #feb2b2;
            }
            .stats {
                background: #f0fff4;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #c6f6d5;
                margin-bottom: 20px;
            }
            .action-buttons {
                margin-top: 10px;
            }
            .detail-btn {
                background: #48bb78;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                margin-right: 5px;
            }
            .detail-btn:hover {
                background: #38a169;
            }
            
            mark {
                background: linear-gradient(135deg, #ffd700, #ffed4e);
                padding: 2px 4px;
                border-radius: 3px;
                font-weight: bold;
                color: #744210;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 独立特許分類検索システム</h1>
            
            <div id="statsSection" class="stats">
                <div id="statsContent">データベース統計を読み込み中...</div>
            </div>
            
            <div class="search-section">
                <h3>💡 キーワード検索</h3>
                <input type="text" id="keywordInput" class="search-input" 
                       placeholder="技術用語を入力（例：画像形成装置、現像剤、センサ）">
                <div>
                    <button class="search-btn" onclick="performSearch()">分類検索</button>
                    <button class="search-btn" onclick="clearResults()" style="background: #718096;">クリア</button>
                </div>
                
                <h4>📝 シンプル検索例</h4>
                <button class="example-btn" onclick="setExample('画像形成装置')">画像形成装置</button>
                <button class="example-btn" onclick="setExample('現像剤')">現像剤</button>
                <button class="example-btn" onclick="setExample('センサ')">センサ</button>
                <button class="example-btn" onclick="setExample('電子写真')">電子写真</button>
                <button class="example-btn" onclick="setExample('トナー')">トナー</button>
                <button class="example-btn" onclick="setExample('レーザー')">レーザー</button>
                
                <h4>🔧 高度検索例</h4>
                <button class="example-btn" onclick="setAdvancedExample('画像 AND 形成')" style="background: #e3f2fd;">AND検索: 画像 AND 形成</button>
                <button class="example-btn" onclick="setAdvancedExample('トナー OR 現像剤')" style="background: #f3e5f5;">OR検索: トナー OR 現像剤</button>
                <button class="example-btn" onclick="setAdvancedExample('車 NEAR3 両')" style="background: #e8f5e8;">近傍検索: 車 NEAR3 両</button>
                <button class="example-btn" onclick="setAdvancedExample('レーザー NOT プリンター')" style="background: #fff3cd;">NOT検索: レーザー NOT プリンター</button>
                
                <div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-radius: 6px; font-size: 13px;">
                    <strong>🔍 高度検索の使い方：</strong><br>
                    <strong>AND:</strong> 「画像 AND 形成」- 両方のキーワードを含む分類<br>
                    <strong>OR:</strong> 「トナー OR 現像剤」- どちらかのキーワードを含む分類<br>
                    <strong>NEAR:</strong> 「車 NEAR3 両」- 車と両が3語以内の距離にある分類<br>
                    <strong>NOT:</strong> 「レーザー NOT プリンター」- レーザーを含むがプリンターを含まない分類
                </div>
            </div>
            
            <div class="search-section">
                <h3>📋 分類コード詳細検索</h3>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <select id="systemSelect" style="padding: 10px; border-radius: 6px; border: 2px solid #cbd5e0;">
                        <option value="IPC">IPC</option>
                        <option value="FI">FI</option>
                        <option value="CPC">CPC</option>
                    </select>
                    <input type="text" id="codeInput" class="search-input" 
                           placeholder="分類コード（例：A01D34/13）" style="margin-bottom: 0;">
                    <button class="search-btn" onclick="getClassificationDetails()" style="white-space: nowrap;">詳細取得</button>
                </div>
                
                <h4>📝 コード例</h4>
                <button class="example-btn" onclick="setCodeExample('IPC', 'A01D34/13')">IPC: A01D34/13</button>
                <button class="example-btn" onclick="setCodeExample('FI', 'A01D34/13')">FI: A01D34/13</button>
                <button class="example-btn" onclick="setCodeExample('CPC', 'A01D34/13')">CPC: A01D34/13</button>
                <button class="example-btn" onclick="getHierarchy('IPC', 'A01D')">階層: IPC A01D</button>
            </div>
            
            <div id="resultsSection" class="results-section">
                <div class="results-header">
                    <div id="resultCount">検索結果</div>
                    <div id="searchTime">検索時間: -</div>
                </div>
                <div id="resultsContainer"></div>
            </div>
        </div>

        <script>
            const API_BASE = '';
            
            // 統計情報を読み込み
            async function loadStats() {
                try {
                    const response = await fetch(`${API_BASE}/stats`);
                    const stats = await response.json();
                    
                    let statsHtml = `📊 データベース統計: 総分類数 ${stats.total_classifications.toLocaleString()} 件`;
                    statsHtml += ` (IPC: ${stats.by_system.IPC.toLocaleString()}, FI: ${stats.by_system.FI.toLocaleString()}, CPC: ${stats.by_system.CPC.toLocaleString()})`;
                    statsHtml += ` | キーワード数: ${stats.total_keywords.toLocaleString()}`;
                    
                    document.getElementById('statsContent').innerHTML = statsHtml;
                } catch (error) {
                    document.getElementById('statsContent').innerHTML = '❌ 統計情報の読み込みに失敗';
                }
            }
            
            // 検索例を設定
            function setExample(keyword) {
                document.getElementById('keywordInput').value = keyword;
            }
            
            // 高度検索例を設定
            function setAdvancedExample(query) {
                document.getElementById('keywordInput').value = query;
            }
            
            function setCodeExample(system, code) {
                document.getElementById('systemSelect').value = system;
                document.getElementById('codeInput').value = code;
            }
            
            // エンターキーで検索
            document.getElementById('keywordInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
            
            document.getElementById('codeInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    getClassificationDetails();
                }
            });
            
            // キーワード検索実行
            async function performSearch() {
                const keyword = document.getElementById('keywordInput').value.trim();
                
                if (!keyword) {
                    alert('検索キーワードを入力してください');
                    return;
                }
                
                const resultsSection = document.getElementById('resultsSection');
                const resultsContainer = document.getElementById('resultsContainer');
                const resultCount = document.getElementById('resultCount');
                const searchTime = document.getElementById('searchTime');
                
                // ローディング表示
                resultsSection.style.display = 'block';
                resultsContainer.innerHTML = '<div class="loading">🔍 検索中...</div>';
                
                try {
                    const startTime = Date.now();
                    const response = await fetch(`${API_BASE}/search/keyword`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            keyword: keyword,
                            systems: ['IPC', 'FI', 'CPC'],
                            limit: 20,
                            highlight: true
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    const endTime = Date.now();
                    
                    // 結果表示
                    resultCount.textContent = `検索結果: ${data.total} 件`;
                    searchTime.textContent = `検索時間: ${endTime - startTime}ms`;
                    
                    if (data.total === 0) {
                        resultsContainer.innerHTML = `
                            <div class="error-message">
                                <h3>📝 検索結果なし</h3>
                                <p>「${keyword}」に該当する分類が見つかりませんでした。</p>
                                <p>別のキーワードで検索してみてください。</p>
                            </div>
                        `;
                        return;
                    }
                    
                    let html = '';
                    data.results.forEach((item, index) => {
                        const systemClass = `system-${item.classification_system.toLowerCase()}`;
                        html += `
                            <div class="result-item">
                                <div>
                                    <span class="system-badge ${systemClass}">${item.classification_system}</span>
                                    <span class="code">${item.code}</span>
                                    <span style="color: #718096; font-size: 14px;">${item.num_documents.toLocaleString()} 件</span>
                                    ${item.match_score ? `<span style="background: #ffd700; color: #744210; padding: 2px 6px; border-radius: 3px; font-size: 12px; font-weight: bold; margin-left: 8px;">⭐ ${item.match_score}</span>` : ''}
                                </div>
                                <div class="title-ja">${item.title_ja_highlighted || item.title_ja || '（日本語タイトルなし）'}</div>
                                <div class="title-en">${item.title_en_highlighted || item.title_en || '（英語タイトルなし）'}</div>
                                
                                ${item.hierarchy_path && item.hierarchy_path.length > 0 ? `
                                    <div style="margin-top: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 12px;">
                                        <strong>階層パス:</strong> ${item.hierarchy_path.map(h => h.code).join(' → ')}
                                    </div>
                                ` : ''}
                                
                                ${item.child_classifications && item.child_classifications.length > 0 ? `
                                    <div style="margin-top: 8px; font-size: 12px; color: #666;">
                                        <strong>下位分類:</strong> ${item.child_classifications.slice(0, 3).map(c => c.code).join(', ')}
                                        ${item.total_children > 3 ? ` (他${item.total_children - 3}件)` : ''}
                                    </div>
                                ` : ''}
                                
                                <div class="action-buttons">
                                    <button class="detail-btn" onclick="getClassificationDetails('${item.classification_system}', '${item.code}')">📋 詳細表示</button>
                                    <button class="detail-btn" onclick="getHierarchy('${item.classification_system}', '${item.code}')">🌲 階層表示</button>
                                </div>
                            </div>
                        `;
                    });
                    
                    resultsContainer.innerHTML = html;
                    
                } catch (error) {
                    console.error('検索エラー:', error);
                    resultsContainer.innerHTML = `
                        <div class="error-message">
                            <h3>🚫 検索エラー</h3>
                            <p>検索でエラーが発生しました: ${error.message}</p>
                            <p>APIサーバーが起動していることを確認してください。</p>
                        </div>
                    `;
                }
            }
            
            // 分類詳細取得
            async function getClassificationDetails(system, code) {
                if (!system) system = document.getElementById('systemSelect').value;
                if (!code) code = document.getElementById('codeInput').value.trim();
                
                if (!code) {
                    alert('分類コードを入力してください');
                    return;
                }
                
                try {
                    const response = await fetch(`${API_BASE}/classification/${system}/${encodeURIComponent(code)}`);
                    
                    if (response.status === 404) {
                        alert(`分類 ${system}_${code} が見つかりませんでした`);
                        return;
                    }
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    let details = `分類詳細情報:\\n\\n`;
                    details += `システム: ${data.classification_system}\\n`;
                    details += `コード: ${data.code}\\n`;
                    details += `レベル: ${data.level}\\n`;
                    details += `日本語: ${data.title_ja || '（なし）'}\\n`;
                    details += `英語: ${data.title_en || '（なし）'}\\n`;
                    details += `文書数: ${data.num_documents}\\n`;
                    
                    if (data.theme) details += `テーマ: ${data.theme}\\n`;
                    if (data.concordance) details += `対応関係: ${data.concordance}\\n`;
                    
                    alert(details);
                    
                } catch (error) {
                    alert(`詳細取得エラー: ${error.message}`);
                }
            }
            
            // 階層情報取得
            async function getHierarchy(system, code) {
                try {
                    const response = await fetch(`${API_BASE}/hierarchy/${system}/${encodeURIComponent(code)}?include_parents=true&include_children=true`);
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    let hierarchy = `階層情報 - ${code} (${system})\\n\\n`;
                    
                    if (data.parents && data.parents.length > 0) {
                        hierarchy += "上位分類:\\n";
                        data.parents.forEach(parent => {
                            hierarchy += `  ${parent.code}: ${parent.title_ja || parent.title_en}\\n`;
                        });
                        hierarchy += "\\n";
                    }
                    
                    if (data.current) {
                        hierarchy += `現在の分類:\\n  ${data.current.code}: ${data.current.title_ja || data.current.title_en}\\n\\n`;
                    }
                    
                    if (data.children && data.children.length > 0) {
                        hierarchy += "下位分類:\\n";
                        data.children.slice(0, 10).forEach(child => {
                            hierarchy += `  ${child.code}: ${child.title_ja || child.title_en}\\n`;
                        });
                        if (data.children.length > 10) {
                            hierarchy += `  ... 他 ${data.children.length - 10} 件\\n`;
                        }
                    }
                    
                    alert(hierarchy);
                    
                } catch (error) {
                    alert(`階層取得エラー: ${error.message}`);
                }
            }
            
            // 結果クリア
            function clearResults() {
                document.getElementById('resultsSection').style.display = 'none';
                document.getElementById('keywordInput').value = '';
                document.getElementById('codeInput').value = '';
            }
            
            // 初期化
            loadStats();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)