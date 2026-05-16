import os
import unittest
from unittest.mock import patch, MagicMock
from lyric_agent import LyricAgent

class TestLyricAgent(unittest.TestCase):
    def setUp(self):
        # Cleanup tmp files
        for f in os.listdir('.'):
            if f.startswith("tmp_"):
                os.remove(f)
        if os.path.exists("lyrics/测试创作.txt"):
            os.remove("lyrics/测试创作.txt")

    def test_creation_flow(self):
        agent = LyricAgent()
        
        # Simulated User Inputs:
        # 1. Model Selection (Enter for default)
        # 2. Style Selection (Enter for default 1)
        # 3. Approve Description (ok)
        # 4. Ask a question (Discussion mode - CHAT)
        # 5. Request Modification (MODIFY - v2)
        # 6. Approve Lyrics (ok)
        # 7. Quit new song (n)
        input_sequence = [
            "", 
            "", 
            "ok", 
            "这个场景有深意吗？", 
            "加入更多雨夜元素", 
            "ok",
            "n"
        ]
        
        with patch('lyric_agent.handle_rich_input', side_effect=input_sequence):
            # Mock Ollama Client
            agent.ollama.get_models = MagicMock(return_value=["qwen3.5:latest"])
            
            # Mock Call & Intent
            agent.ollama.call = MagicMock(side_effect=[
                "这是一个赛博朋克的雨夜场景描述。", # Description v1
                "场景深度分析：雨夜代表了内心的挣扎。", # Chat response
                "这是加入雨夜元素后的修改版场景。", # Description v2
                "这是根据场景创作的初始歌词。",   # Lyrics v1
                "测试创作"                         # Title generation
            ])
            
            agent.ollama.check_intent = MagicMock(side_effect=[
                ("APPROVE", "ok"),                # Approve Description
                ("CHAT", "这个场景有深意吗？"),    # Discussion
                ("MODIFY", "加入更多雨夜元素"),    # Modify Description
                ("APPROVE", "ok")                 # Approve Lyrics
            ])

            # Manual Step Execution
            agent.handle_init()
            self.assertEqual(agent.style, "Funk/Swagger") # Assuming it's first in song_styles.md
            
            agent.handle_song_description() # v1 -> APPROVE -> State moves to SONG_LYRICS
            self.assertEqual(agent.state, "SONG_LYRICS")
            
            agent.handle_song_lyrics() # v1 -> CHAT
            agent.handle_song_lyrics() # v1 -> MODIFY -> v2
            self.assertEqual(agent.lyrics_index, 2)
            
            agent.handle_song_lyrics() # v2 -> APPROVE -> Saving
            
            # Verify Output
            self.assertTrue(os.path.exists("lyrics/测试创作.txt"))
            print("\n[lyric_agent 测试成功]: 构思、讨论、修改及保存逻辑运行正常。")

if __name__ == "__main__":
    unittest.main()
