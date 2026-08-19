我希望能设计一套完整的自动化 Agent 工作流，以满足复杂任务的完整实现流程

1. 帮我调研已有的 best-practice，doc，design，repo（2025Sep 以后的，必要时如果需要 clone 仓库，ssh clone 到/home/agent/reference）
2. 需要整合各种设计原则 SOLID，TDD，Code-Rules(如home/agent/workspace/code-rules)以及其他优秀的设计核心理念
3. 需要能利用 SubAgent 的能力，来让每个 Agent 专注在同一个任务上，避免上下文污染
4. 还需要有 AgentTeams 来进行职责划分来分别进行 Review，Research，Design，Test
5. 任务需要进行精细化的分解，来保证任务本身的每个 Stage，Wave 都足够单元化
6. 在每个层级内，主 Agent 都不能去进行具体的开发，调研，测试，review 等，主 Agent 的意义就在于如何推进任务进行，具体的任务都需要对应的 sub Agent来进行，例如主 plan 的 Plan-Main-Agent 要做的事情就是调度 Wave-Main-Agent完成对应 Wave，依次类推
7. 这个工作流需要内置不同模式，例如对于本地仓库的处理方式（如无需发布 release 等），github 仓库的处理方式(跨平台构建，readme，userguide，github action， github io page， online demo 等)，其他 git 仓库处理方式（提供 mr 等）
8. 还需要有提前决策阶段的设计，尽量在真正的研发阶段开始前，将需要用户解决和提供的信息尽早提出
9. 最终希望整个 workflow 能在前期确认好各种信息后，能连续运行并尽可能完成设计任务，避免遇到中断项以阻碍研发

可以参考 ~/.cursor 下的各种历史 plan （尤其是最近一周内的）来抽象共性经验
可以参考这个任务的记录/home/agent/workspace/EchoAccess/.local

当前 task 不进行代码实现和深入调研，仅仅用于指导方向，后续 plan 制定后，build 阶段才需要进行具体的实现和调研

另外这个工作流的最终产品产出形式（也帮我调研产品形式这一点）：
1. 我希望是一个多工具兼容的形式（claude code， cursor， Copilot）skill组合
2. 要避免一个超长的 skill，尽量是一个多级索引来管控上下文的形式
3. 副产物需要有一个 mvp 的单一文件 skill，以最小功能来实现上述功能（面向 cursor 的shared-script 功能）
4. 整体产出需要有两个体系，面向 Agent 的体系（英文，skill+rules+知识组合形式），和面向人类开发者的可读可理解的经验形式（中英文，文档+demo page）
5. 预留出未来作为 VSCode 插件化的能力入口

还需要调研“research-design-review-refine”工作流以及“design-plan-impl-review-test-refine-testgate-release”工作流以及其他工作流，补充工作流的实际形式以及工作流体系如何整合和支持不同类型工作流 