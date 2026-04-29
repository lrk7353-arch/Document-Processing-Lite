from langgraph.graph import StateGraph, END
from agent.langgraph.state import AgentState
from agent.langgraph.nodes.file_node import FileNode
from agent.langgraph.nodes.model_node import ModelNode
from agent.langgraph.nodes.compliance_node import ComplianceNode
from agent.langgraph.nodes.error_node import ErrorNode
from agent.utils.logger import logger
from sqlalchemy.orm import Session

def build_agent_graph(db: Session) -> StateGraph:
    """
    构建智能体状态机图（严格遵循《数据契约与状态机.docx》业务流程）
    流程：文件上传 → 模型调度 → 合规检查 → 结果生成
    """
    # 初始化节点
    file_node = FileNode(db=db)
    model_node = ModelNode(db=db)
    compliance_node = ComplianceNode(db=db)
    error_node = ErrorNode(db=db)

    # 创建状态图
    graph = StateGraph(AgentState)

    # 1. 添加节点：文件上传相关
    graph.add_node("start_file_upload", file_node.start_file_upload)
    graph.add_node("handle_file_complete", file_node.handle_file_upload_complete)

    # 2. 添加节点：模型调度相关
    graph.add_node("dispatch_model", model_node.dispatch_model)
    graph.add_node("handle_algorithm_result", model_node.handle_algorithm_result)

    # 3. 添加节点：合规检查相关
    graph.add_node("run_compliance_check", compliance_node.run_compliance_check)
    graph.add_node("generate_final_result", compliance_node.generate_final_result)

    # 4. 添加节点：错误处理
    graph.add_node("handle_error", error_node.langgraph_error_handler)

    # 定义状态流转规则（对齐文档业务流程）
    # 初始流：开始文件上传 → 处理文件完成
    graph.set_entry_point("start_file_upload")
    graph.add_edge("start_file_upload", "handle_file_complete")

    # 文件处理流：文件完成 → 模型调度（成功）/ 错误处理（失败）
    def file_router(state: AgentState) -> str:
        if state.agent_state == "failed":
            return "handle_error"
        return "dispatch_model"
    graph.add_conditional_edges("handle_file_complete", file_router)

    # 模型调度流：模型调度 → 算法结果（成功）/ 错误处理（失败）
    def model_dispatch_router(state: AgentState) -> str:
        if state.agent_state == "failed":
            return "handle_error"
        return "handle_algorithm_result"
    graph.add_conditional_edges("dispatch_model", model_dispatch_router)

    # 算法结果流：算法结果 → 合规检查（成功）/ 错误处理（失败）
    def algorithm_result_router(state: AgentState) -> str:
        if state.agent_state == "failed":
            return "handle_error"
        return "run_compliance_check"
    graph.add_conditional_edges("handle_algorithm_result", algorithm_result_router)

    # 合规检查流：合规检查 → 生成最终结果（成功）/ 错误处理（失败）
    def compliance_router(state: AgentState) -> str:
        if state.agent_state == "failed":
            return "handle_error"
        return "generate_final_result"
    graph.add_conditional_edges("run_compliance_check", compliance_router)

    # 最终流：生成结果 → 结束 / 错误处理 → 结束
    graph.add_edge("generate_final_result", END)
    graph.add_edge("handle_error", END)

    logger.info("LangGraph智能体状态机构建完成", extra={"processId": "system", "algorithmTaskId": "system"})
    return graph