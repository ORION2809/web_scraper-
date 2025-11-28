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

## CRITICAL ANTI-HALLUCINATION RULES:
1. ONLY extract information that is EXPLICITLY stated in the source text
2. DO NOT invent or infer ANY values not directly stated
3. If something is not mentioned, use null or empty arrays - NEVER guess
4. Quote exact text from source when possible
5. When in doubt, leave it empty

## EXTRACTION GUIDE:

### programName
- The official name of the loyalty program (e.g., "Starbucks Rewards", "MyMcDonald's Rewards")
- Must be explicitly stated on the page

### description  
- The official program description or tagline
- Use exact text from the source

### strategy.industry
- The business category (e.g., "Quick Service Restaurant", "Coffee", "Fast Food")
- Infer from brand context if obvious (Starbucks = Coffee)

### strategy.programType
- Usually "B2C Customer Loyalty" for consumer programs
- Could be "Membership", "Subscription" if stated

### strategy.goals
- Business objectives like "Increase purchase frequency", "Improve retention"
- ONLY if explicitly stated or clearly implied

### strategy.behaviors
- Actions customers can take: "Purchases", "App usage", "Referrals", "Social sharing", "Reviews"
- ONLY include if the program explicitly rewards these behaviors

### strategy.audience
- Target customer segments mentioned: "Frequent visitors", "Mobile app users", "New customers"
- ONLY if explicitly described

### strategy.channels
- How customers interact: "Mobile app", "Website", "In-store POS", "Email"
- Include channels explicitly mentioned

### design.segments
- Named customer segments with criteria (e.g., "Gold Members: 5000+ points annually")
- Include approx_users ONLY if stated
- MOST programs don't explicitly define segments - leave empty if not stated

### design.tiers
- ONLY membership tier levels explicitly named (e.g., "Bronze", "Silver", "Gold", "Platinum")
- Each tier needs: name, range (point threshold), multiplierText (earning multiplier), benefits
- DO NOT confuse redemption levels (25 Stars, 100 Stars) with membership tiers
- If no tiers are explicitly named, leave empty

### design.incentives
- Promotional campaigns and special offers
- Examples: "Birthday Reward", "Referral Bonus", "Double Points Days", "Welcome Offer", "Free Refills"
- Include name and description
- IMPORTANT: Extract ALL benefits and special offers mentioned

### design.rewards.loyalty_points
- The earning rate: "1 point per $1", "2 Stars per $1", "10 points per $1"
- Extract EXACTLY as stated

### design.rewards.achievement_badges
- Gamification badges/achievements with Name, Criteria, and Reward
- Examples: "First Purchase Badge - Complete first order - 50 bonus points"
- ONLY if explicitly mentioned

### design.rewards.gift_cards
- Gift card redemption options with Name (value), redemption_points, validity_days
- ONLY if explicitly listed

### design.rewards.catalog_products
- Items available for point redemption
- Name: exact item name or category
- point_cost: exact point cost as stated
- IMPORTANT: Extract ALL redemption tiers mentioned (e.g., 25 Stars, 100 Stars, 200 Stars, 300 Stars, 400 Stars)
- Include ALL items at each tier level
- This is where redemption items go (NOT membership tiers)

## OUTPUT FORMAT:
Return valid JSON matching this exact structure:
{
  "programName": "string or null",
  "description": "string or null",
  "strategy": {
    "industry": "string or null",
    "programType": "string or null",
    "goals": ["string array - only if stated"],
    "behaviors": ["string array - only if rewarded"],
    "audience": ["string array - only if stated"],
    "channels": ["string array - only if mentioned"]
  },
  "design": {
    "segments": [
      {"name": "string", "criteria": "string", "approx_users": number_or_null}
    ],
    "tiers": [
      {"name": "string", "range": "string", "multiplierText": "string", "benefits": ["string"]}
    ],
    "incentives": [
      {"name": "string", "description": "string or null"}
    ],
    "rewards": {
      "loyalty_points": {"points_per_dollar": "string or null"},
      "achievement_badges": [
        {"Name": "string", "Criteria": "string", "Reward": "string"}
      ],
      "gift_cards": [
        {"Name": "string", "redemption_points": "string", "validity_days": "string"}
      ],
      "catalog_products": [
        {"Name": "string", "point_cost": "string"}
      ]
    }
  }
}

REMEMBER: Extract only what IS there. Leave empty what ISN'T. Never invent."""


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
        
        # Truncate full_text if too long (keep under ~20k tokens, ~25k chars)
        text = parsed.full_text[:25000]
        
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
