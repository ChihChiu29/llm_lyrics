import os
import unittest
import re
from unittest.mock import patch, MagicMock
from suno_tag_agent import SunoTagAgent

class TestTagAgent(unittest.TestCase):
    def setUp(self):
        # Cleanup
        for f in os.listdir('.'):
            if f.startswith("tmp_tag_"):
                os.remove(f)
        if os.path.exists("lyrics_tagged/标注测试.txt"):
            os.remove("lyrics_tagged/标注测试.txt")

    def test_tagging_flow(self):
        agent = SunoTagAgent()
        
        # 1. Model Selection
        # 2. Title Input
        # 3. Lyrics Input
        # 4. Approve Tags (ok) -> Move to Styles
        # 5. Approve Styles (ok) -> Save
        # 6. Exit
        input_sequence = [
            "", 
            "标注测试", 
            "这是一段测试用的歌词内容。", 
            "ok", 
            "ok",
            "n"
        ]
        
        with patch('suno_tag_agent.handle_rich_input', side_effect=input_sequence):
            agent.ollama.get_models = MagicMock(return_value=["qwen3.5:latest"])
            
            # call outputs
            agent.ollama.call = MagicMock(side_effect=[
                "标注测试\n\n[Intro, slow]\n这是一段测试用的歌词内容。", # Initial Tags v1
                "- Style 1: Cinematic atmospheric trap beat\n- Style 2: Melancholic piano ballad", # Style Suggestion sv1
                "APPROVE" # Meta generation call (naming or similar if any, though tagging doesn't have it)
            ])
            
            agent.ollama.check_intent = MagicMock(side_effect=[
                ("APPROVE", "ok"), # Approve Tags
                ("APPROVE", "ok")  # Approve Styles
            ])

            agent.handle_init()
            agent.handle_input_title()
            agent.handle_input_lyrics()
            
            agent.handle_tagging() # v1 -> APPROVE -> state moves to STYLE_DISCUSSION
            self.assertEqual(agent.state, "STYLE_DISCUSSION")
            
            agent.handle_style_discussion() # sv1 -> APPROVE -> Save
            
            self.assertTrue(os.path.exists("lyrics_tagged/标注测试.txt"))
            print("\n[suno_tag_agent 测试成功]: 标注、风格生成及合并保存逻辑运行正常。")

if __name__ == "__main__":
    unittest.main()
