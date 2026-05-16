import os
import unittest
from unittest.mock import patch, MagicMock
from critic_agent import LyricCriticAgent

class TestLyricCriticAgent(unittest.TestCase):
    def setUp(self):
        # 确保 lyrics 目录存在且有一个测试文件
        if not os.path.exists("lyrics"):
            os.makedirs("lyrics")
        self.test_file = "lyrics/test_song_for_critic.txt"
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write("Test Song Title\n\nVerse 1\nLine 1\nLine 2\n\nChorus\nLine 3\nLine 4")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_critic_flow(self):
        agent = LyricCriticAgent()
        
        # 准备模拟输入序列
        # 1. 模型选择 (回车默认)
        # 2. 选择文件 (1)
        # 3. 批准评价 (ok)
        # 4. 结束后的退出 (n)
        input_sequence = [
            "", 
            "1", 
            "ok",
            "n"
        ]
        
        with patch('critic_agent.handle_rich_input', side_effect=input_sequence):
            # 模拟 Ollama 的回复
            agent.ollama.call = MagicMock(return_value="This is a professional critique.")
            agent.ollama.check_intent = MagicMock(return_value=("APPROVE", "ok"))

            # 运行 Agent
            agent.handle_init()
            # 我们需要确保 handle_select_file 能选到我们的测试文件
            # 假设测试文件是列表中的第一个
            agent.handle_select_file()
            self.assertEqual(agent.song_title, "test_song_for_critic.txt")
            
            agent.handle_critic_loop()
            self.assertEqual(agent.state, "ENDING")
            
            print("\n[测试成功]: 批评家代理的基础流程、文件加载及意图识别均正常工作。")

if __name__ == "__main__":
    unittest.main()
