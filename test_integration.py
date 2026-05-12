import os
import unittest
from unittest.mock import patch, MagicMock
from lyric_agent import LyricAgent

class TestLyricAgentIntegration(unittest.TestCase):
    def setUp(self):
        # 清理环境
        for f in os.listdir('.'):
            if f.startswith("tmp_song_"):
                os.remove(f)

    def test_auto_improve_lyrics(self):
        agent = LyricAgent()
        agent.lyrics_index = 1
        
        # 模拟批评家不满意，然后满意
        # 1. get_critic_feedback (第一次反馈)
        # 2. check_p (NO - 不满意)
        # 3. mod_prompt (修改歌词)
        # 4. get_critic_feedback (第二次反馈)
        # 5. check_p (YES - 满意)
        
        mock_responses = [
            "Your rhythm is bad.", # feedback 1
            "NO",                  # check_satisfied 1
            "Revised Lyrics",      # mod_lyrics
            "Much better.",        # feedback 2
            "YES"                  # check_satisfied 2
        ]
        
        agent.ollama.call = MagicMock(side_effect=mock_responses)
        
        initial_lyrics = "Original Lyrics"
        final_lyrics = agent.auto_improve_with_critic(initial_lyrics, stage="LYRICS")
        
        self.assertEqual(final_lyrics, "Revised Lyrics")
        self.assertEqual(agent.lyrics_index, 2)
        self.assertTrue(os.path.exists("tmp_song_lyrics_02.md"))
        print("\n[测试成功]: 自动优化循环正确执行，且版本号与文件保存均符合预期。")

if __name__ == "__main__":
    unittest.main()
