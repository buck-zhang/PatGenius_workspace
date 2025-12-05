import sys
sys.path.insert(0, '.')
from patent_search_executor import PatentSearchExecutor

# テストインスタンス作成
executor = PatentSearchExecutor(
    'tests/performance_test/JP2013224028A_keywords.json',
    'tests/performance_test/JP2013224028A_classification.json'
)

# バリデーションテスト
test_codes = [
    # FI codes
    ('B29K445:00', 'FI', False, 'コロンを含む'),
    ('B41L47/48 A', 'FI', False, '空白を含む'),
    ('D01F6/52', 'FI', True, '標準FIコード'),
    ('B41J2/16201', 'FI', True, '標準FIコード'),
    
    # IPC codes  
    ('B41J2/01101', 'IPC', False, 'スラッシュ後5桁(詳細すぎる)'),
    ('B41J2/1601', 'IPC', False, 'スラッシュ後4桁(詳細すぎる)'),
    ('B41J31/06', 'IPC', True, 'スラッシュ後2桁(標準)'),
    ('B41J2/01', 'IPC', True, 'スラッシュ後2桁(標準)'),
    ('B41J2/135', 'IPC', True, 'スラッシュ後3桁(標準)'),
    
    # Fterm codes
    ('2C056HA24', 'Fterm', True, '標準Fterm'),
]

print("=== 拡張バリデーションテスト ===\n")
print(f"{'Code':<20} {'Type':<8} {'Expected':<10} {'Result':<10} {'Reason':<30}")
print("=" * 85)

all_pass = True
for code, class_type, expected, reason in test_codes:
    result = executor._is_valid_classification_code(code, class_type)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    
    if result != expected:
        all_pass = False
    
    print(f"{code:<20} {class_type:<8} {str(expected):<10} {str(result):<10} {reason:<30} {status}")

print("\n" + "=" * 85)
if all_pass:
    print("✓ 全てのテストがパスしました")
else:
    print("✗ 一部のテストが失敗しました")
    
