from app.schemas.tools import ToolArgs
TOOLS=[{"type":"function","function":{"name":n,"description":d,"parameters":ToolArgs.model_json_schema()}} for n,d in [
 ("query_classrooms","查询指定日期空闲教室"),("query_courses","查询指定日期可旁听课程"),
 ("recommend_dishes","工具根据日期、预算和口味筛选排序菜品"),("query_secondhand","查询在售二手物品"),("search_knowledge","检索校园规范与知识")]]
