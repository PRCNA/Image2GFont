"""LM Format Enforcer core adapter for Transformers 5 tokenizers."""
from lmformatenforcer import JsonSchemaParser,TokenEnforcer,TokenEnforcerTokenizerData


def tokenizer_data(tokenizer):
    special=set(tokenizer.all_special_ids)
    ids=[i for i in range(len(tokenizer)) if i not in special]
    prefix=tokenizer.encode('0',add_special_tokens=False)[-1]
    plain=tokenizer.batch_decode([[i] for i in ids],clean_up_tokenization_spaces=False)
    contextual=tokenizer.batch_decode([[prefix,i] for i in ids],clean_up_tokenization_spaces=False)
    tokens=[(i,context[1:],len(context[1:])>len(text)) for i,text,context in zip(ids,plain,contextual)]
    def decode(values):return tokenizer.decode(values,clean_up_tokenization_spaces=False).rstrip('\ufffd')
    return TokenEnforcerTokenizerData(tokens,decode,tokenizer.eos_token_id,False,len(tokenizer))


def prefix_function(data,schema):
    enforcer=TokenEnforcer(data,JsonSchemaParser(schema))
    def allowed(batch_id,sent):return enforcer.get_allowed_tokens(sent.tolist()).allowed_tokens
    return allowed
