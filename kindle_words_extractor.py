#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import csv
import os
import sys
import argparse
from typing import Tuple, List, Dict, Optional, Set
from tqdm import tqdm
import re
import requests
import json

# 导入配置文件
try:
    from config import AI_API_CONFIG
except ImportError:
    # 默认配置，以防配置文件不存在
    AI_API_CONFIG = {
        "API_KEY": "",
        "API_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "MODEL": "qwen-turbo-latest"
    }
    print("警告: 未找到配置文件config.py，将使用默认配置")


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
        .ai-explanation {
            margin-top: 12px;
            background-color: #f1f8ff;
            padding: 10px;
            border-radius: 6px;
            border-left: 3px solid #58a6ff;
        }
        .ai-content {
            white-space: pre-line;
        }
        .ai-error {
            color: #d63384;
            font-style: italic;
            margin-top: 8px;
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


def _translate_with_ai(word: str, sentence: str, api_key: str = None, api_url: str = None, model: str = None) -> str:
    """使用阿里云通义千问API翻译单词在例句中的含义"""
    # 如果没有例句，直接返回空字符串
    if not sentence or not word:
        return ""
    
    # 使用配置文件中的API信息，如果未指定则使用默认值
    api_key = api_key or AI_API_CONFIG.get("API_KEY", "")
    api_url = api_url or AI_API_CONFIG.get("API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    model = model or AI_API_CONFIG.get("MODEL", "qwen-turbo-latest")
    
    # 确保API密钥存在
    if not api_key:
        return "<div class='ai-error'>未配置API密钥，请在config.py中设置API_KEY</div>"
    
    # 移除HTML标签
    clean_sentence = re.sub(r'<.*?>', '', sentence)
    
    # 构建请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 构建请求内容
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": "你是一个精通英语的助手，专门提供单词在特定例句中的含义解释。请保持回答简洁准确。"
            },
            {
                "role": "user", 
                "content": f"解释单词'{word}'在例句中的含义并翻译例句：\n[单词解释]：简洁说明词义。[例句翻译]：翻译成中文\n例句：{clean_sentence}"
            }
        ]
    }
    
    try:
        # 发送API请求
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response_data = response.json()
        
        # 检查响应是否成功
        if response.status_code == 200 and 'choices' in response_data:
            # 提取AI的回复
            ai_explanation = response_data['choices'][0]['message']['content']
            
            # 格式化显示 - 删除机器人图标
            formatted_explanation = f"""<div class="ai-explanation">
                <div class="ai-content">{ai_explanation}</div>
            </div>"""
            
            return formatted_explanation
        else:
            # 如果请求失败，返回错误信息
            error_msg = response_data.get('error', {}).get('message', '未知错误')
            return f"<div class='ai-error'>API请求失败: {error_msg}</div>"
    
    except Exception as e:
        return f"<div class='ai-error'>API请求出错: {str(e)}</div>"


def get_existing_words(csv_file: str) -> Set[str]:
    """获取现有CSV文件中已存在的单词"""
    if not os.path.exists(csv_file):
        return set()
    
    existing_words = set()
    try:
        with open(csv_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            # 跳过标题行（如果有）
            try:
                first_row = next(reader)
                # 检查是否有列标题
                if len(first_row) == 2 and first_row[0] != first_row[1]:
                    # 这可能是标题行，不处理
                    pass
                else:
                    # 尝试从HTML内容中提取单词
                    word_html = first_row[0]
                    # 尝试多种提取模式
                    patterns = [
                        r'<div class="word-display">(.*?)</div>',
                        r'word-title">(.*?)</div>',
                        r'<strong>(.*?)</strong>'
                    ]
                    for pattern in patterns:
                        word_match = re.search(pattern, word_html)
                        if word_match:
                            word = word_match.group(1).lower().strip()
                            existing_words.add(word)
                            break
            except StopIteration:
                pass  # 文件是空的
                
            # 读取剩余行
            for row in reader:
                if len(row) >= 1:
                    # 尝试从HTML内容中提取单词
                    word_html = row[0]
                    # 尝试多种提取模式
                    extracted = False
                    patterns = [
                        r'<div class="word-display">(.*?)</div>',
                        r'word-title">(.*?)</div>',
                        r'<strong>(.*?)</strong>'
                    ]
                    for pattern in patterns:
                        word_match = re.search(pattern, word_html)
                        if word_match:
                            word = word_match.group(1).lower().strip()
                            existing_words.add(word)
                            extracted = True
                            break
                    
                    # 如果没有通过正则提取到，尝试更简单的HTML清理方式
                    if not extracted and word_html:
                        # 移除所有HTML标签
                        clean_word = re.sub(r'<.*?>', '', word_html).strip().lower()
                        if clean_word and len(clean_word) < 30:  # 避免添加整个文本块
                            words = re.findall(r'\b[a-zA-Z]+\b', clean_word)
                            if words:
                                existing_words.add(words[0])  # 添加第一个单词
        
        # 添加常见词形变化以提高匹配率
        expanded_words = set(existing_words)
        for word in existing_words:
            # 处理常见的词形变化
            if word.endswith('s') and len(word) > 2:
                expanded_words.add(word[:-1])  # 可能的单数形式
            if word.endswith('es') and len(word) > 3:
                expanded_words.add(word[:-2])  # 可能的单数形式
            if word.endswith('ed') and len(word) > 3:
                expanded_words.add(word[:-2])  # 可能的原形
                if len(word) > 4 and word[-3] == word[-4]:  # 双写辅音，如stopped->stop
                    expanded_words.add(word[:-3])
            if word.endswith('ing') and len(word) > 4:
                expanded_words.add(word[:-3])  # 可能的原形
                expanded_words.add(word[:-3] + 'e')  # 如writing->write
        
        existing_words = expanded_words
        print(f"从现有CSV文件中读取了 {len(existing_words)} 个单词（包含词形变化）")
        return existing_words
    except Exception as e:
        print(f"读取现有CSV文件时出错: {e}")
        return set()


def process_kindle_vocabulary(kindle_db: str, dict_db: str, output_file: Optional[str] = None, limit: Optional[int] = None, 
                              ai_translation: bool = True, incremental_update: bool = True) -> Tuple[str, int]:
    """处理Kindle词汇并添加词典释义"""
    # 如果没有指定输出文件，使用默认名称
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(kindle_db))[0]
        output_file = f"{base_name}_processed.csv"
    
    try:
        # 获取现有CSV文件中的单词
        existing_words = set()
        if incremental_update and os.path.exists(output_file):
            existing_words = get_existing_words(output_file)
        
        # 1. 提取Kindle单词
        kindle_extractor = KindleVocabularyExtractor(kindle_db)
        all_words_list = kindle_extractor.extract_words(limit)
        kindle_extractor.close()
        
        # 如果是增量更新，过滤出新单词
        if incremental_update and existing_words:
            total_kindle_words = len(all_words_list)
            new_words_list = []
            
            # 初始化词典以便查询单词原型
            dictionary = ECDICTDictionary(dict_db)
            
            for word_info in all_words_list:
                word = word_info['单词'].lower()
                stem = word_info['原型'].lower() if word_info['原型'] else word
                
                # 收集所有可能的单词形式
                possible_forms = set([word, stem])
                
                # 尝试从词典获取更多可能的形式
                try:
                    # 查询词典以获取可能的词形变化
                    self_cursor = dictionary.cursor
                    self_cursor.execute(
                        "SELECT exchange FROM stardict WHERE LOWER(word) = LOWER(?)", 
                        (stem,)
                    )
                    exchange_result = self_cursor.fetchone()
                    
                    # 尝试提取可能的原型
                    if exchange_result and exchange_result[0]:
                        exchange = exchange_result[0]
                        for part in exchange.split('/'):
                            if ':' in part:
                                _, forms = part.split(':', 1)
                                if forms:
                                    for form in forms.split('/'):
                                        possible_forms.add(form.lower())
                except Exception:
                    pass  # 忽略词典查询错误
                
                # 检查是否所有可能的形式都不在现有单词列表中
                is_new_word = True
                for form in possible_forms:
                    if form in existing_words:
                        is_new_word = False
                        break
                
                if is_new_word:
                    new_words_list.append(word_info)
            
            # 关闭词典连接
            dictionary.close()
            
            duplicate_words = total_kindle_words - len(new_words_list)
            print(f"Kindle数据库中共有 {total_kindle_words} 个单词")
            print(f"其中与CSV文件重复的单词数: {duplicate_words} 个")
            print(f"需要处理的新单词数: {len(new_words_list)} 个")
            words_list = new_words_list
        else:
            words_list = all_words_list
        
        # 如果没有新单词需要处理，直接返回
        if not words_list:
            print("没有新单词需要处理，退出程序")
            return output_file, 0
        
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
                    
                    # 如果启用了AI翻译，获取单词在例句中的含义解释
                    ai_explanation = ""
                    if ai_translation and source_text:
                        print(f"\n正在翻译单词 '{word}' 在例句中的含义...")
                        ai_explanation = _translate_with_ai(word, source_text)
                        # 如果AI解释为空，则不添加
                        if ai_explanation:
                            # 减小例句和AI解释之间的间隔
                            highlighted_source = f"{highlighted_source}<br>{ai_explanation}"
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
        if incremental_update and os.path.exists(output_file):
            # 增量更新模式：读取现有内容，追加新内容
            existing_rows = []
            try:
                with open(output_file, 'r', newline='', encoding='utf-8') as infile:
                    reader = csv.reader(infile)
                    for row in reader:
                        if row:  # 确保行不为空
                            existing_rows.append(row)
            except Exception as e:
                print(f"读取现有CSV文件内容时出错: {e}")
                existing_rows = []
            
            # 将新行添加到现有内容中
            with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.writer(outfile)
                # 写入现有内容
                for row in existing_rows:
                    writer.writerow(row)
                # 写入新内容
                for row_dict in new_rows:
                    writer.writerow([row_dict['单词'], row_dict['释义与例句']])
        else:
            # 全新写入模式
            with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                fieldnames = ['单词', '释义与例句']
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                # 不写入CSV标题行
                # writer.writeheader()
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
    parser.add_argument('--no-ai', action='store_true', help='禁用AI翻译功能')
    parser.add_argument('-f', '--full', action='store_true', help='全量更新模式，处理所有单词')
    
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
        print(f"AI翻译功能: {'已禁用' if args.no_ai else '已启用'}")
        print(f"更新模式: {'全量更新' if args.full else '增量更新'}")
        output_file, count = process_kindle_vocabulary(
            args.kindle_db,
            args.dict_db,
            args.output,
            args.limit,
            not args.no_ai,  # 取反，如果--no-ai被指定，则禁用AI翻译
            not args.full    # 取反，如果--full被指定，则不使用增量更新
        )
        print(f"\n处理完成！")
        print(f"成功处理 {count} 个单词")
        print(f"结果已保存到: {output_file}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 