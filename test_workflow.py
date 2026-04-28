import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
from lyric_modify_agent import LyricModifyAgent

class TestLyricAgentWorkflow(unittest.TestCase):
    def setUp(self):
        # 清理测试环境
        for f in os.listdir('.'):
            if f.startswith("tmp_mod_"):
                os.remove(f)
        if os.path.exists("lyrics_modified/测试歌曲.txt"):
            os.remove("lyrics_modified/测试歌曲.txt")

    def test_full_modify_flow(self):
        agent = LyricModifyAgent()
        
        # 准备模拟输入序列
        # 1. 模型选择 (回车默认)
        # 2. 标题 (测试歌曲)
        # 3. 原始歌词
        # 4. 修改建议 (触发应用修改)
        # 5. 回退指令 (v1)
        # 6. 确认回退后的 ok (批准)
        # 7. 结束后的退出 (n)
        input_sequence = [
            "", 
            "测试歌曲", 
            "第一行歌词\n第二行歌词", 
            "让它更伤感一点", 
            "v1", 
            "ok",
            "n"
        ]
        
        with patch('lyric_modify_agent.handle_rich_input', side_effect=input_sequence):
            # 模拟 Ollama 的回复
            # 第一次回复: 修改后的歌词 (v2)
            # 第二次回复: 意图判定 (CHAT/MODIFY/APPROVE) -> 这里模拟判定为 v1 回退后的 ok 为 APPROVE
            mock_call = MagicMock(side_effect=[
                "这是伤感的修改后歌词\n第二行也很伤感", # call for MODIFY
                "APPROVE" # check_intent for 'ok'
            ])
            agent.ollama.call = mock_call
            
            # 由于 check_intent 也是调用 call，我们直接 mock check_intent 更省事
            agent.ollama.check_intent = MagicMock(side_effect=[
                ("MODIFY", "让它更伤感一点"), # 对应输入 4
                ("APPROVE", "ok")             # 对应输入 6
            ])

            # 运行 Agent (跳过主循环，手动按序执行阶段以防死循环)
            agent.handle_init()
            agent.handle_input_title()
            agent.handle_input_lyrics()
            
            # 进入修改循环 - 执行第一次修改
            agent.handle_modify_loop() # 处理 "让它更伤感一点"
            self.assertEqual(agent.version, 2)
            self.assertTrue(os.path.exists("tmp_mod_测试歌曲_v02.txt"))

            # 进入修改循环 - 执行回退
            agent.handle_modify_loop() # 处理 "v1"
            self.assertEqual(agent.version, 1)
            
            # 进入修改循环 - 执行批准
            agent.handle_modify_loop() # 处理 "ok"
            
            # 最终验证
            self.assertTrue(os.path.exists("lyrics_modified/测试歌曲.txt"))
            print("\n[测试成功]: 流程闭环、版本管理、回退逻辑及文件保存均正常工作。")

if __name__ == "__main__":
    unittest.main()
