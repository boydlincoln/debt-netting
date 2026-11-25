# 本体规则维护说明

`debt_ontology.owl` 是系统抵销规则的单一可信来源。可直接用
[Protégé](https://protege.stanford.edu/) 打开、编辑与保存，无需改动 Python 代码。

## 一、文件结构

| 部分 | 说明 |
| --- | --- |
| `owl:Class` | 主体、债权债务、资产、清偿方案、优先顺位债权、不可抵销债务 |
| `owl:ObjectProperty` | `hasDebtor`、`hasCreditor`、`guaranteedBy`、`settlesDebt` |
| `owl:DatatypeProperty` | 金额、本金、利息、到期日、争议、查封、禁止抵销、顺位分组等 |
| `swrl:Imp` | 抵销资格规则；每条规则带 `debt:ruleId`、`debt:severity`、`debt:message`、`debt:legalBasis` |
| 派生属性 | `hasMatured`、`hasPriority`、`hasSelfDealing`、`hasAmountPositive`，由本地引擎按基准日与业务数据计算 |

严重度语义：

- `blocking`：命中即阻断抵销，债务进入未入池清单；
- `review`：命中即转人工复核，同样不进入轧差池；
- `info`：仅提示（例如优先顺位分组隔离），不阻断。

## 二、新增一条规则

例如“超过诉讼时效的债务不得抵销”：

1. 在数据属性区增加 `hasTimeBarred` 声明（布尔）；
2. 在文件末尾追加：

```xml
<swrl:Imp rdf:about="#R8_TimeBarredNotSetoff">
  <debt:ruleId>R8</debt:ruleId>
  <debt:order rdf:datatype="http://www.w3.org/2001/XMLSchema#int">80</debt:order>
  <debt:ruleName xml:lang="zh">超过诉讼时效的债务不得抵销</debt:ruleName>
  <debt:severity rdf:datatype="http://www.w3.org/2001/XMLSchema#string">blocking</debt:severity>
  <debt:message xml:lang="zh">该笔债务已超过诉讼时效，需人工核实后处理。</debt:message>
  <debt:legalBasis xml:lang="zh">诉讼时效届满的债权能否抵销存在争议，应按人工审查处理。</debt:legalBasis>
  <swrl:body>
    <rdf:Description>
      <rdf:type rdf:resource="http://www.w3.org/2003/11/swrl#ClassAtom"/>
      <swrl:classPredicate rdf:resource="#DebtObligation"/>
      <swrl:argument1><swrl:Variable rdf:about="#d"/></swrl:argument1>
    </rdf:Description>
    <rdf:Description>
      <rdf:type rdf:resource="http://www.w3.org/2003/11/swrl#DatatypePropertyAtom"/>
      <swrl:propertyPredicate rdf:resource="#hasTimeBarred"/>
      <swrl:argument1><swrl:Variable rdf:about="#d"/></swrl:argument1>
      <swrl:argument2 rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</swrl:argument2>
    </rdf:Description>
  </swrl:body>
  <swrl:head>
    <rdf:Description>
      <rdf:type rdf:resource="http://www.w3.org/2003/11/swrl#ClassAtom"/>
      <swrl:classPredicate rdf:resource="#IneligibleDebt"/>
      <swrl:argument1><swrl:Variable rdf:about="#d"/></swrl:argument1>
    </rdf:Description>
  </swrl:head>
</swrl:Imp>
```

3. 在 `app/ontology.py` 的 `_derived()` 中补充 `hasTimeBarred` 的计算（若它是派生属性）；
4. 在“系统设置 → 本体与 SWRL 规则”点击“重新加载本体”，或重启服务。

## 三、支持的表达式子集

当前本地推理器支持：

- `ClassAtom(DebtObligation, ?d)`
- `DatatypePropertyAtom(property, ?d, 布尔/字符串字面量)`
- 规则 body 为多个原子的合取；head 仅用于规则展示（结论由 `debt:severity` 决定）

比较、算术等复杂 SWRL 内置谓词暂不支持。若规则需要日期或金额比较，建议在本地引擎中
计算成布尔派生属性（例如 `hasMatured`）后再由 SWRL 引用，以保持规则可读与可审计。

## 四、修改后的验证

```powershell
python -m unittest tests.test_core.OntologyRulesTest -v
```

或启动服务后打开“设置 → 重新加载本体”，在工作台查看规则数量与名称是否更新。
