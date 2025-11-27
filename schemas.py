"""
Pydantic schemas for loyalty program data.
Defines the canonical structure for extracted loyalty information.
Based on FastBite Rewards structure - uses camelCase for JSON output.
All fields are always present (null if not found).
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ============================================================
# STRATEGY SECTION
# ============================================================

class Strategy(BaseModel):
    """Program strategy and business goals"""
    industry: Optional[str] = None
    programType: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    behaviors: List[str] = Field(default_factory=list)
    audience: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)


# ============================================================
# DESIGN SECTION
# ============================================================

class Segment(BaseModel):
    """Customer segment definition"""
    name: Optional[str] = None
    criteria: Optional[str] = None
    approx_users: Optional[int] = None


class Tier(BaseModel):
    """Loyalty program tier/level"""
    name: Optional[str] = None
    range: Optional[str] = None
    multiplierText: Optional[str] = None
    benefits: List[str] = Field(default_factory=list)


class Incentive(BaseModel):
    """Campaign/incentive program"""
    name: Optional[str] = None
    description: Optional[str] = None


class LoyaltyPoints(BaseModel):
    """Points earning configuration"""
    points_per_dollar: Optional[str] = None


class AchievementBadge(BaseModel):
    """Achievement/badge reward"""
    Name: Optional[str] = None
    Criteria: Optional[str] = None
    Reward: Optional[str] = None


class GiftCard(BaseModel):
    """Gift card redemption option"""
    Name: Optional[str] = None
    redemption_points: Optional[str] = None
    validity_days: Optional[str] = None


class CatalogProduct(BaseModel):
    """Product available for redemption"""
    Name: Optional[str] = None
    point_cost: Optional[str] = None


class Rewards(BaseModel):
    """All reward types available"""
    loyalty_points: Optional[LoyaltyPoints] = None
    achievement_badges: List[AchievementBadge] = Field(default_factory=list)
    gift_cards: List[GiftCard] = Field(default_factory=list)
    catalog_products: List[CatalogProduct] = Field(default_factory=list)


class Design(BaseModel):
    """Program design configuration"""
    segments: List[Segment] = Field(default_factory=list)
    tiers: List[Tier] = Field(default_factory=list)
    incentives: List[Incentive] = Field(default_factory=list)
    rewards: Optional[Rewards] = None


# ============================================================
# MAIN LOYALTY PROGRAM SCHEMA
# ============================================================

class LoyaltyProgram(BaseModel):
    """Complete loyalty program schema - FastBite Rewards structure"""
    # Basic info
    programName: Optional[str] = None
    description: Optional[str] = None
    
    # Strategy (always present)
    strategy: Optional[Strategy] = None
    
    # Design (always present)
    design: Optional[Design] = None
    
    # Metadata (added by scraper)
    brand: Optional[str] = None
    url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    raw_text_length: Optional[int] = None


class ParsedContent(BaseModel):
    """Intermediate parsed content before LLM classification"""
    url: str
    brand: str
    title: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    list_items: List[str] = Field(default_factory=list)
    tables: List[List[List[str]]] = Field(default_factory=list)
    json_ld: Optional[dict] = None
    meta_description: Optional[str] = None
    full_text: str = ""
