"""
Classifier module - uses LLM to extract structured loyalty program data.
Supports OpenAI API (GPT-4/GPT-3.5) and can be extended for other providers.
"""
import os
import json
from typing import Optional
from datetime import datetime

from schemas import ParsedContent, LoyaltyProgram


# System prompt for loyalty program extraction - FastBite Rewards structure
# STRICT: No hallucination - only extract what is explicitly stated
SYSTEM_PROMPT = """You are an expert at extracting structured loyalty program information from web page content.

CRITICAL RULES:
1. ONLY extract information that is EXPLICITLY stated in the source text
2. DO NOT invent tier names like "Green" or "Gold" unless they are explicitly mentioned
3. DO NOT infer point ranges or thresholds that aren't stated
4. Extract exact values as written in the source
5. If something is not mentioned, use null or empty arrays

KEY DISTINCTIONS:
- "Redemption levels" (e.g., "25 Stars for X, 100 Stars for Y") should go in catalog_products, NOT tiers
- "Membership tiers" (e.g., "Bronze", "Silver", "Gold") should go in tiers ONLY if explicitly named as membership levels
- Extract earning rates exactly as stated (e.g., "2 Stars per $1")

Extract the following (ONLY if explicitly stated):
1. **Program Name**: Exact official name
2. **Description**: Exact description from source
3. **Strategy**: Industry type, program type, channels mentioned
4. **Tiers**: ONLY if page explicitly names membership tier levels
5. **Rewards/Redemption**: 
   - Points earning rate (exact as stated)
   - Catalog products: Items available for redemption with their point costs
   - Gift cards if mentioned
   - Badges/achievements if mentioned
6. **Incentives**: Special offers, birthday rewards, bonuses mentioned

Return valid JSON:
{
  "programName": "string or null - exact name",
  "description": "string or null - exact description",
  "strategy": {
    "industry": "string or null",
    "programType": "string or null",
    "goals": [],
    "behaviors": [],
    "audience": [],
    "channels": ["string - channels mentioned like 'Mobile app', 'Website', 'In-store'"]
  },
  "design": {
    "segments": [],
    "tiers": [],
    "incentives": [
      {
        "name": "string - e.g., 'Birthday Reward'",
        "description": "string - exact description"
      }
    ],
    "rewards": {
      "loyalty_points": {
        "points_per_dollar": "string - exact earning rate e.g., '2 Stars per $1'"
      },
      "achievement_badges": [],
      "gift_cards": [],
      "catalog_products": [
        {
          "Name": "string - redemption item name",
          "point_cost": "string - e.g., '25 Stars', '100 Stars'"
        }
      ]
    }
  }
}

Extract what IS there. Leave empty what ISN'T there. Do not invent."""


def classify_with_openai(parsed: ParsedContent, model: str = "gpt-4o-mini") -> Optional[dict]:
    """
    Send parsed content to OpenAI for classification.
    Requires OPENAI_API_KEY environment variable.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Skipping LLM classification.")
        return None
    
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Truncate full_text if too long (keep under ~12k tokens)
        text = parsed.full_text[:15000]
        
        user_prompt = f"""Extract loyalty program information from this {parsed.brand} webpage:

URL: {parsed.url}

--- PAGE CONTENT ---
{text}
--- END CONTENT ---

Return the structured JSON extraction."""
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        return json.loads(result_text)
        
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response as JSON: {e}")
        return None
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None


def build_loyalty_program(parsed: ParsedContent, llm_result: Optional[dict]) -> LoyaltyProgram:
    """
    Build a LoyaltyProgram object from parsed content and LLM classification.
    Always returns full structure with null values for missing fields.
    """
    from schemas import (
        Strategy, Design, Segment, Tier, Incentive, 
        Rewards, LoyaltyPoints, AchievementBadge, GiftCard, CatalogProduct
    )
    
    # Default empty structure
    default_strategy = Strategy(
        industry=None,
        programType=None,
        goals=[],
        behaviors=[],
        audience=[],
        channels=[]
    )
    
    default_rewards = Rewards(
        loyalty_points=LoyaltyPoints(points_per_dollar=None),
        achievement_badges=[],
        gift_cards=[],
        catalog_products=[]
    )
    
    default_design = Design(
        segments=[],
        tiers=[],
        incentives=[],
        rewards=default_rewards
    )
    
    if llm_result:
        # Build Strategy from LLM result
        strategy_data = llm_result.get("strategy", {}) or {}
        strategy = Strategy(
            industry=strategy_data.get("industry"),
            programType=strategy_data.get("programType"),
            goals=strategy_data.get("goals", []) or [],
            behaviors=strategy_data.get("behaviors", []) or [],
            audience=strategy_data.get("audience", []) or [],
            channels=strategy_data.get("channels", []) or []
        )
        
        # Build Design from LLM result
        design_data = llm_result.get("design", {}) or {}
        
        segments = [
            Segment(
                name=seg.get("name"),
                criteria=seg.get("criteria"),
                approx_users=seg.get("approx_users")
            ) for seg in (design_data.get("segments", []) or [])
        ]
        
        tiers = [
            Tier(
                name=tier.get("name"),
                range=tier.get("range"),
                multiplierText=tier.get("multiplierText"),
                benefits=tier.get("benefits", []) or []
            ) for tier in (design_data.get("tiers", []) or [])
        ]
        
        incentives = [
            Incentive(
                name=inc.get("name"),
                description=inc.get("description")
            ) for inc in (design_data.get("incentives", []) or [])
        ]
        
        # Build Rewards
        rewards_data = design_data.get("rewards", {}) or {}
        loyalty_points_data = rewards_data.get("loyalty_points", {}) or {}
        loyalty_points = LoyaltyPoints(
            points_per_dollar=loyalty_points_data.get("points_per_dollar")
        )
        
        achievement_badges = [
            AchievementBadge(
                Name=badge.get("Name"),
                Criteria=badge.get("Criteria"),
                Reward=badge.get("Reward")
            ) for badge in (rewards_data.get("achievement_badges", []) or [])
        ]
        
        gift_cards = [
            GiftCard(
                Name=gc.get("Name"),
                redemption_points=gc.get("redemption_points"),
                validity_days=gc.get("validity_days")
            ) for gc in (rewards_data.get("gift_cards", []) or [])
        ]
        
        catalog_products = [
            CatalogProduct(
                Name=prod.get("Name"),
                point_cost=prod.get("point_cost")
            ) for prod in (rewards_data.get("catalog_products", []) or [])
        ]
        
        rewards = Rewards(
            loyalty_points=loyalty_points,
            achievement_badges=achievement_badges,
            gift_cards=gift_cards,
            catalog_products=catalog_products
        )
        
        design = Design(
            segments=segments,
            tiers=tiers,
            incentives=incentives,
            rewards=rewards
        )
        
        return LoyaltyProgram(
            programName=llm_result.get("programName"),
            description=llm_result.get("description"),
            strategy=strategy,
            design=design,
            brand=parsed.brand,
            url=parsed.url,
            scraped_at=datetime.utcnow(),
            raw_text_length=len(parsed.full_text)
        )
    else:
        # Fallback: return full structure with nulls
        return LoyaltyProgram(
            programName=parsed.title,
            description=None,
            strategy=default_strategy,
            design=default_design,
            brand=parsed.brand,
            url=parsed.url,
            scraped_at=datetime.utcnow(),
            raw_text_length=len(parsed.full_text)
        )


def classify(parsed: ParsedContent, skip_llm: bool = False, model: str = "gpt-4o-mini") -> LoyaltyProgram:
    """
    Main classification function.
    Takes ParsedContent and returns structured LoyaltyProgram.
    """
    llm_result = None
    
    if not skip_llm:
        print(f"  Classifying with LLM ({model})...")
        llm_result = classify_with_openai(parsed, model=model)
        if llm_result:
            print(f"  ✓ LLM extraction complete")
        else:
            print(f"  ✗ LLM extraction failed, using fallback")
    else:
        print(f"  Skipping LLM classification (--skip-llm)")
    
    return build_loyalty_program(parsed, llm_result)
