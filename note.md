从第四章开始,前面都是简单llm基础

# [第四章 智能体经典范式构建](https://datawhalechina.github.io/hello-agents/#/./chapter4/第四章 智能体经典范式构建?id=第四章-智能体经典范式构建)

- **ReAct (Reasoning and Acting)：** 一种将“思考”和“行动”紧密结合的范式，让智能体边想边做，动态调整。
- **Plan-and-Solve：** 一种“三思而后行”的范式，智能体首先生成一个完整的行动计划，然后严格执行。
- **Reflection：** 一种赋予智能体“反思”能力的范式，通过自我批判和修正来优化结果。.

[llm_client](\code\chapter4\llm_client.py) 配置好.env后,就可以使用这个方法调用llm,我这里用的反代理,