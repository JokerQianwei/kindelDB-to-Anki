#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kindle单词提取和词典查询工具
功能：
1. 从Kindle词汇数据库中提取单词
2. 使用ECDICT查询详细释义
3. 生成包含单词信息和词典释义的CSV文件
"""

import sqlite3
import csv
import os
import sys
import argparse
from typing import Tuple, List, Dict, Optional
from tqdm import tqdm
import re


class KindleVocabularyExtractor:
    """从Kindle数据库提取词汇"""
    
    def __init__(self, db_file: str):
        if not os.path.exists(db_file):
            raise FileNotFoundError(f"找不到Kindle数据库: {db_file}")
        
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def extract_words(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """提取单词和来源"""
        query = """
        SELECT 
            w.word as word,
            w.stem as stem,
            GROUP_CONCAT(l.usage, '|||') as usages
        FROM WORDS w
        LEFT JOIN LOOKUPS l ON w.id = l.word_key
        GROUP BY w.word
        ORDER BY w.timestamp DESC
        """
        
        if limit:
            query += f"\nLIMIT {limit}"
        
        words_list = []
        try:
            self.cursor.execute(query)
            
            for row in self.cursor:
                word = row['word']
                stem = row['stem']
                if ':' in word:  # 处理类似 'en:word' 格式的单词
                    word = word.split(':', 1)[1]
                
                # 处理来源列表
                usages = row['usages']
                if usages:
                    # 分割多个来源，只保留前三个
                    usage_list = usages.split('|||')[:3]
                    # 清理每个来源并合并
                    cleaned_usages = '<br>---<br>'.join(u.strip() for u in usage_list if u.strip())
                else:
                    cleaned_usages = ''
                
                words_list.append({
                    '单词': word,
                    '原型': stem,
                    '来源': cleaned_usages
                })
            
            return words_list
        
        except sqlite3.Error as e:
            raise Exception(f"从Kindle数据库提取单词时出错: {e}")
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()


class ECDICTDictionary:
    """ECDICT词典查询"""
    
    def __init__(self, db_path: str):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"找不到词典数据库: {db_path}")
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._cache = {}
        
        # 添加索引以提升查询速度
        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_lower ON stardict(LOWER(word))")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_sw ON stardict(sw)")
            self.conn.commit()
        except sqlite3.Error:
            pass  # 如果索引已存在则忽略
    
    def lookup_word(self, word: str) -> Tuple[str, Optional[str]]:
        """查询单词释义，返回(释义HTML, 词形变化原型)元组"""
        word_lower = word.lower()
        if word_lower in self._cache:
            return self._cache[word_lower]
        
        # 首先尝试精确匹配
        query = """
        SELECT word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio
        FROM stardict 
        WHERE LOWER(word) = LOWER(?)
        """
        
        self.cursor.execute(query, (word,))
        result = self.cursor.fetchone()
        
        if not result:
            # 如果找不到，尝试模糊匹配（去除连字符等）
            stripped_word = ''.join(c.lower() for c in word if c.isalnum())
            query = """
            SELECT word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio
            FROM stardict 
            WHERE sw = ?
            """
            self.cursor.execute(query, (stripped_word,))
            result = self.cursor.fetchone()
        
        if result:
            # 提取词形变化中的原型
            exchange = result[10]  # exchange字段
            word_root = None
            if exchange:
                for part in exchange.split('/'):
                    if part.startswith('0:'):  # 0: 表示原型
                        word_root = part.split(':', 1)[1]
                        break
            
            entry = self._format_entry(result)
            self._cache[word_lower] = (entry, word_root)
            return (entry, word_root)
        return ("未找到释义", None)
    
    def _format_entry(self, result: tuple) -> str:
        """格式化词典条目"""
        word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio = result
        
        # 基础样式
        css_style = """
        <style>
        .dict-entry, .word-entry {
            font-family: "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 15px 0;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section {
            margin: 10px 0;
            padding: 8px;
            border-left: 3px solid #007bff;
            background-color: white;
            border-radius: 4px;
        }
        .section-title {
            color: #0056b3;
            font-weight: bold;
            margin-bottom: 5px;
            font-size: 1.1em;
        }
        .phonetic {
            color: #6c757d;
            font-family: "Courier New", monospace;
            margin-right: 10px;
        }
        .pos {
            color: #28a745;
            font-weight: 500;
        }
        .freq-info {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .freq-item {
            background-color: #e9ecef;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            color: #495057;
        }
        .definition {
            margin: 5px 0;
            padding-left: 10px;
            border-left: 2px solid #dee2e6;
            color: #212529;
            text-align: left;
        }
        .chinese {
            color: #d63384;
        }
        .english {
            color: #0d6efd;
        }
        .word-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .source {
            color: #6c757d;
            margin-top: 8px;
            padding: 8px;
            border-left: 2px solid #dee2e6;
            text-align: left;
        }
        </style>
        """
        
        entry = [css_style, '<div class="dict-entry">']
        
        # 1. 音标和词性
        if phonetic or pos:
            section = ['<div class="section">']
            section.append('<div class="section-title">发音与词性</div>')
            if phonetic:
                section.append(f'<span class="phonetic">[{phonetic}]</span>')
            if pos:
                section.append(f'<span class="pos">{pos}</span>')
            section.append('</div>')
            entry.append(''.join(section))
        
        # 2. 释义（移到词频信息之前）
        if translation or definition:
            section = ['<div class="section">']
            section.append('<div class="section-title">释义</div>')
            if translation:
                section.append('<div class="definition chinese">')
                section.append(translation.replace('\\n', '<br>'))
                section.append('</div>')
            if definition:
                section.append('<div class="definition english">')
                section.append(definition.replace('\\n', '<br>'))
                section.append('</div>')
            section.append('</div>')
            entry.append(''.join(section))
        
        # 3. 词频信息
        freq_info = []
        if collins or oxford or bnc or frq or tag:
            section = ['<div class="section">']
            section.append('<div class="section-title">词频信息</div>')
            section.append('<div class="freq-info">')
            
            if collins:
                stars = "⭐" * int(collins)
                freq_info.append(f'<span class="freq-item">柯林斯星级：{stars}</span>')
            if oxford:
                freq_info.append('<span class="freq-item">牛津核心词汇</span>')
            if bnc:
                freq_info.append(f'<span class="freq-item">BNC词频：{bnc}</span>')
            if frq:
                freq_info.append(f'<span class="freq-item">词频顺序：{frq}</span>')
            if tag:
                freq_info.append(f'<span class="freq-item">标签：{tag}</span>')
            
            section.append(''.join(freq_info))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        # 4. 词形变化
        if exchange:
            section = ['<div class="section">']
            section.append('<div class="section-title">词形变化</div>')
            exchange_parts = []
            for part in exchange.split('/'):
                if ':' in part:
                    label, forms = part.split(':')
                    labels = {
                        'p': '过去式',
                        'd': '过去分词',
                        'i': '现在分词',
                        '3': '第三人称单数',
                        'r': '比较级',
                        't': '最高级',
                        's': '复数',
                        '0': '原形',
                        '1': '类别1',
                        'f': '未来式'
                    }
                    label = labels.get(label, label)
                    exchange_parts.append(f'<span class="freq-item">{label}: {forms}</span>')
            section.append('<div class="freq-info">')
            section.append(''.join(exchange_parts))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        # 5. 补充信息
        if detail:
            section = ['<div class="section">']
            section.append('<div class="section-title">补充信息</div>')
            section.append('<div class="definition">')
            section.append(detail.replace('\\n', '<br>'))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        entry.append('</div>')
        return '\n'.join(entry)
    
    def format_entry_with_source(self, result: tuple, source_text: str) -> str:
        """格式化带有来源的词典条目"""
        word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio = result
        
        # 基础样式
        css_style = """
        <style>
        .dict-entry, .word-entry {
            font-family: "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 15px 0;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section {
            margin: 10px 0;
            padding: 8px;
            border-left: 3px solid #007bff;
            background-color: white;
            border-radius: 4px;
        }
        .phonetic {
            color: #6c757d;
            font-family: "Courier New", monospace;
            margin-right: 10px;
        }
        .pos {
            color: #28a745;
            font-weight: 500;
        }
        .freq-info {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .freq-item {
            background-color: #e9ecef;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            color: #495057;
        }
        .definition {
            margin: 5px 0;
            padding-left: 10px;
            border-left: 2px solid #dee2e6;
            color: #212529;
            text-align: left;
        }
        .chinese {
            color: #d63384;
        }
        .english {
            color: #0d6efd;
        }
        .word-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .source {
            color: #6c757d;
            margin-top: 8px;
            padding: 8px;
            border-left: 2px solid #dee2e6;
            text-align: left;
        }
        .highlight {
            color: #d63384;
            font-weight: bold;
            padding: 0 2px;
        }
        </style>
        """
        
        entry = [css_style, '<div class="dict-entry">']
        
        # 1. 音标和词性
        if phonetic or pos:
            section = ['<div class="section">']
            if phonetic:
                section.append(f'<span class="phonetic">[{phonetic}]</span>')
            if pos:
                section.append(f'<span class="pos">{pos}</span>')
            section.append('</div>')
            entry.append(''.join(section))
        
        # 2. 来源例句 (新增部分)
        if source_text:
            section = ['<div class="section">']
            section.append(f'<div class="source">{source_text}</div>')
            section.append('</div>')
            entry.append(''.join(section))
        
        # 3. 释义
        if translation or definition:
            section = ['<div class="section">']
            if translation:
                section.append('<div class="definition chinese">')
                section.append(translation.replace('\\n', '<br>'))
                section.append('</div>')
            if definition:
                section.append('<div class="definition english">')
                section.append(definition.replace('\\n', '<br>'))
                section.append('</div>')
            section.append('</div>')
            entry.append(''.join(section))
        
        # 4. 词频信息
        freq_info = []
        if collins or oxford or bnc or frq or tag:
            section = ['<div class="section">']
            section.append('<div class="freq-info">')
            
            if collins:
                stars = "⭐" * int(collins)
                freq_info.append(f'<span class="freq-item">柯林斯星级：{stars}</span>')
            if oxford:
                freq_info.append('<span class="freq-item">牛津核心词汇</span>')
            if bnc:
                freq_info.append(f'<span class="freq-item">BNC词频：{bnc}</span>')
            if frq:
                freq_info.append(f'<span class="freq-item">词频顺序：{frq}</span>')
            if tag:
                freq_info.append(f'<span class="freq-item">标签：{tag}</span>')
            
            section.append(''.join(freq_info))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        # 5. 词形变化
        if exchange:
            section = ['<div class="section">']
            exchange_parts = []
            for part in exchange.split('/'):
                if ':' in part:
                    label, forms = part.split(':')
                    labels = {
                        'p': '过去式',
                        'd': '过去分词',
                        'i': '现在分词',
                        '3': '第三人称单数',
                        'r': '比较级',
                        't': '最高级',
                        's': '复数',
                        '0': '原形',
                        '1': '类别1',
                        'f': '未来式'
                    }
                    label = labels.get(label, label)
                    exchange_parts.append(f'<span class="freq-item">{label}: {forms}</span>')
            section.append('<div class="freq-info">')
            section.append(''.join(exchange_parts))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        # 6. 补充信息
        if detail:
            section = ['<div class="section">']
            section.append('<div class="definition">')
            section.append(detail.replace('\\n', '<br>'))
            section.append('</div></div>')
            entry.append(''.join(section))
        
        entry.append('</div>')
        return '\n'.join(entry)
    
    def close(self):
        self.conn.close()


def _highlight_word(text: str, word: str) -> str:
    """在文本中用颜色标记目标单词及其变体"""
    # 处理可能的词形变化
    word_patterns = [
        word,  # 原形
        word + 's',  # 复数
        word + 'es',  # 复数变体
        word + 'ed',  # 过去式
        word + 'd',  # 过去式变体
        word + 'ing',  # 现在分词
        word[:-1] + 'ing' if word.endswith('e') else '',  # 去e加ing
        word + word[-1] + 'ing' if word[-1] in 'aeiou' and len(word) > 1 else '',  # 双写字母加ing
    ]
    
    # 移除空字符串
    word_patterns = [p for p in word_patterns if p]
    
    # 构建正则表达式，不区分大小写
    pattern = '|'.join(map(re.escape, word_patterns))
    pattern = f'\\b({pattern})\\b'
    
    # 使用HTML标签添加颜色样式
    highlighted = re.sub(
        pattern,
        lambda m: f'<span class="highlight">{m.group()}</span>',
        text,
        flags=re.IGNORECASE
    )
    
    return highlighted


def process_kindle_vocabulary(kindle_db: str, dict_db: str, output_file: Optional[str] = None, limit: Optional[int] = None) -> Tuple[str, int]:
    """处理Kindle词汇并添加词典释义"""
    # 如果没有指定输出文件，使用默认名称
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(kindle_db))[0]
        output_file = f"{base_name}_processed.csv"
    
    try:
        # 1. 提取Kindle单词
        print("正在从Kindle数据库提取单词...")
        kindle_extractor = KindleVocabularyExtractor(kindle_db)
        words_list = kindle_extractor.extract_words(limit)
        kindle_extractor.close()
        
        # 2. 初始化词典
        dictionary = ECDICTDictionary(dict_db)
        
        # 3. 处理每个单词并添加词典释义
        total_words = len(words_list)
        print(f"\n开始查询 {total_words} 个单词的词典释义...")
        
        # 准备新的行数据
        new_rows = []
        with tqdm(total=total_words, desc="处理进度") as pbar:
            for word_info in words_list:
                word = word_info['单词']
                stem = word_info['原型'] or word  # 使用原型查询，如果没有原型则使用原单词
                source_text = word_info['来源']
                
                # 处理例句，只保留第一个例句
                if source_text and '---' in source_text:
                    source_text = source_text.split('---')[0].strip()
                
                # 高亮处理例句
                if source_text:
                    # 高亮显示原句中的所有相关形式
                    highlighted_source = _highlight_word(source_text, word)
                    
                    # 如果stem不同于word，也高亮stem
                    if stem and stem != word:
                        highlighted_source = _highlight_word(highlighted_source, stem)
                else:
                    highlighted_source = ""
                
                # 使用stem查询词典
                query = stem
                self_cursor = dictionary.cursor
                self_cursor.execute(
                    "SELECT word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio "
                    "FROM stardict WHERE LOWER(word) = LOWER(?)", 
                    (query,)
                )
                result = self_cursor.fetchone()
                
                if not result:
                    # 如果找不到，尝试模糊匹配（去除连字符等）
                    stripped_word = ''.join(c.lower() for c in query if c.isalnum())
                    self_cursor.execute(
                        "SELECT word, phonetic, translation, definition, pos, collins, oxford, tag, bnc, frq, exchange, detail, audio "
                        "FROM stardict WHERE sw = ?", 
                        (stripped_word,)
                    )
                    result = self_cursor.fetchone()
                
                # 确定最终显示的单词
                display_word = word
                
                # 获取合适的词典释义
                if result:
                    # 提取词形变化中的原型
                    exchange = result[10]  # exchange字段
                    if exchange:
                        for part in exchange.split('/'):
                            if part.startswith('0:'):  # 0: 表示原型
                                root = part.split(':', 1)[1]
                                # 如果有原型单词，优先使用它
                                display_word = root
                                break
                    
                    # 使用新方法生成带有例句的词典条目
                    dictionary_entry = dictionary.format_entry_with_source(result, highlighted_source)
                else:
                    # 如果找不到词典释义
                    css_style = """
                    <style>
                    .dict-entry {
                        font-family: "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
                        line-height: 1.6;
                        margin: 15px 0;
                        padding: 15px;
                        border-radius: 8px;
                        background-color: #f8f9fa;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .section {
                        margin: 10px 0;
                        padding: 8px;
                        border-left: 3px solid #007bff;
                        background-color: white;
                        border-radius: 4px;
                    }
                    .source {
                        color: #6c757d;
                        margin-top: 8px;
                        padding: 8px;
                        border-left: 2px solid #dee2e6;
                        text-align: left;
                    }
                    </style>
                    """
                    dictionary_entry = f"{css_style}<div class='dict-entry'>"
                    if highlighted_source:
                        dictionary_entry += f"<div class='section'><div class='source'>{highlighted_source}</div></div>"
                    dictionary_entry += "<div class='section'>未找到释义</div></div>"
                
                # 为第一个字段创建美化的单词显示
                word_html = f"""
                <style>
                .word-container {{
                    font-family: "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
                    line-height: 1.6;
                    margin: 15px 0;
                    padding: 15px;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .word-display {{
                    font-size: 1.8em;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 10px 0;
                    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                }}
                </style>
                <div class="word-container">
                    <div class="word-display">{display_word}</div>
                </div>
                """
                
                # 添加到新的行数据
                new_rows.append({
                    '单词': word_html,
                    '释义与例句': dictionary_entry
                })
                
                pbar.update(1)
        
        # 4. 写入输出文件
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['单词', '释义与例句']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_rows)
        
        # 5. 关闭词典
        dictionary.close()
        
        return output_file, total_words
    
    except Exception as e:
        print(f"处理过程中出错: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Kindle单词提取和词典查询工具')
    parser.add_argument('kindle_db', nargs='?', default='vocab.db',
                      help='Kindle词汇数据库文件路径 (.db)，默认为当前目录下的vocab.db')
    parser.add_argument('dict_db', nargs='?', default='stardict.db',
                      help='ECDICT词典数据库文件路径，默认为当前目录下的stardict.db')
    parser.add_argument('-o', '--output', help='输出CSV文件路径（可选）')
    parser.add_argument('-l', '--limit', type=int, help='限制处理的单词数量（可选）')
    
    args = parser.parse_args()
    
    # 检查文件是否存在，如果不存在则提供更详细的错误信息
    if not os.path.exists(args.kindle_db):
        print(f"错误: 找不到Kindle数据库文件: {args.kindle_db}")
        print("请确保文件存在，或使用 -h 参数查看帮助信息")
        print("示例用法:")
        print("1. 使用默认文件名：python kindle_words_extractor.py")
        print("2. 指定文件路径：python kindle_words_extractor.py path/to/vocab.db path/to/stardict.db")
        sys.exit(1)
    
    if not os.path.exists(args.dict_db):
        print(f"错误: 找不到词典数据库文件: {args.dict_db}")
        print("请确保文件存在，或使用 -h 参数查看帮助信息")
        print("您可以从以下地址下载ECDICT词典数据库：")
        print("https://github.com/skywind3000/ECDICT/releases")
        sys.exit(1)
    
    try:
        print(f"开始处理...\n")
        print(f"使用Kindle数据库: {args.kindle_db}")
        print(f"使用词典数据库: {args.dict_db}")
        output_file, count = process_kindle_vocabulary(
            args.kindle_db,
            args.dict_db,
            args.output,
            args.limit
        )
        print(f"\n处理完成！")
        print(f"成功处理 {count} 个单词")
        print(f"结果已保存到: {output_file}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 