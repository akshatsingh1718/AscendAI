import boto3
import os
import json

class BedrockLLM:
    def __init__(self):
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name= os.environ['AWS_DEFAULT_REGION']
        )
        self.model_id = "openai.gpt-oss-safeguard-120b"

    def _extract_bedrock_response_text(self, resp_obj) -> str:
        try:
            if not resp_obj:
                return ''
            # common modern shape
            out = resp_obj.get('output') if isinstance(resp_obj, dict) else None
            if isinstance(out, dict):
                msg = out.get('message')
                if isinstance(msg, dict):
                    content = msg.get('content')
                    if isinstance(content, list) and content:
                        for c in content:
                            if isinstance(c, dict) and 'text' in c and isinstance(c['text'], str):
                                return c['text']
                            if isinstance(c, str):
                                return c
                            # nested content
                            if isinstance(c, dict) and isinstance(c.get('content'), list):
                                for sub in c.get('content'):
                                    if isinstance(sub, dict) and isinstance(sub.get('text'), str):
                                        return sub.get('text')
            # fallback: search recursively for any 'text' key
            def search_for_text(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == 'text' and isinstance(v, str):
                            return v
                        res = search_for_text(v)
                        if res:
                            return res
                if isinstance(obj, list):
                    for el in obj:
                        res = search_for_text(el)
                        if res:
                            return res
                return None

            res = search_for_text(resp_obj)
            if isinstance(res, str):
                return res
        except Exception:
            pass
        # final fallback
        try:
            return json.dumps(resp_obj)
        except Exception:
            return str(resp_obj)

    def generate_text(self, prompt: str, maxTokens: int= 2000) -> str:
        response= self.bedrock.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": maxTokens, "temperature": 0.0},
                # responseFormat={"type": "json"}
            )
        return self._extract_bedrock_response_text(response)

    def generate_json(self, prompt: str, maxTokens: int= 2000) -> str:
        response = self.generate_text(prompt, maxTokens)

        return self._fallback_to_json_conversion(response)
    

    def _fallback_to_json_conversion(self, response_text: str):

        # Clean common markdown fences
        clean_text = response_text.strip()
        if clean_text.startswith('```'):
            parts = clean_text.split('```')
            if len(parts) >= 2:
                clean_text = parts[1]
                if clean_text.startswith('json'):
                    clean_text = clean_text[4:]
        clean_text = clean_text.strip()

        leads = []
        # Try to parse JSON directly; if it fails, ask the LLM to reformat into valid JSON
        try:
            leads = json.loads(clean_text)
        except json.JSONDecodeError:
            print(f"⚠️ Initial JSON parse failed asking LLM to reformat output into valid JSON...")
            fixer_prompt = (
                "The assistant produced the following response which is intended to be a JSON array of lead objects, "
                "but it is not valid JSON. Please convert it into a valid JSON array of objects with these keys: "
                "company_name, industry, description, why_payu, source_url, company_size, lead_score (0-100). "
                "Preserve as much information as possible from the original output. Return ONLY the JSON array, no explanations.\n\n"
                f"RAW_OUTPUT:\n{clean_text}"
            )

            try:
                # resp_fix = self.bedrock.converse(
                #     modelId=self.model_id,
                #     messages=[{"role": "user", "content": [{"text": fixer_prompt}]}],
                #     inferenceConfig={"maxTokens": 3000, "temperature": 0.0}
                # )
                # fixed_text = self._extract_bedrock_response_text(resp_fix).strip()
                fixed_text = self.generate_text(fixer_prompt, maxTokens=3000).strip()
                if fixed_text.startswith('```'):
                    parts = fixed_text.split('```')
                    if len(parts) >= 2:
                        fixed_text = parts[1]
                        if fixed_text.startswith('json'):
                            fixed_text = fixed_text[4:]
                fixed_text = fixed_text.strip()
                leads = json.loads(fixed_text)
                clean_text = fixed_text
                print(f"✅ LLM reformatted output into valid JSON")
            except Exception as e:
                print(f"⚠️ JSON-fixer LLM failed for: {e}")
                # re-raise to be handled by outer exception logic
                raise
        return leads