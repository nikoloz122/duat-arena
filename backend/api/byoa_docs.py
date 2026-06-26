"""OpenAPI spec and integration examples for BYOA remote agents."""

from __future__ import annotations

import json
from typing import Any, Dict

OPENAPI_SPEC: Dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {
        "title": "DUAT Arena BYOA Agent API",
        "version": "1.0.0",
        "description": (
            "Contract for remote trading agents integrated with DUAT Arena. "
            "Implement POST /decide on your server; DUAT calls it once per simulation tick."
        ),
    },
    "paths": {
        "/decide": {
            "post": {
                "summary": "Return a trading decision for the current tick",
                "operationId": "decide",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DecideRequest"},
                            "example": {
                                "tick": 12,
                                "market": {
                                    "current_price": 95.2,
                                    "liquidity": 850.0,
                                    "volatility": 0.12,
                                    "market_sentiment": -0.15,
                                    "total_volume": 120.0,
                                },
                                "portfolio": {
                                    "cash": 500.0,
                                    "position": 5.2,
                                    "equity": 995.0,
                                    "exposure": 495.0,
                                    "status": "active",
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Valid decision",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DecideResponse"},
                                "example": {
                                    "action": "hold",
                                    "confidence": 0.72,
                                    "size": 0.5,
                                    "reason": "Volatility elevated; waiting for clarity.",
                                },
                            }
                        },
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "MarketState": {
                "type": "object",
                "required": [
                    "current_price",
                    "liquidity",
                    "volatility",
                    "market_sentiment",
                    "total_volume",
                ],
                "properties": {
                    "current_price": {"type": "number"},
                    "liquidity": {"type": "number"},
                    "volatility": {"type": "number"},
                    "market_sentiment": {"type": "number"},
                    "total_volume": {"type": "number"},
                },
            },
            "PortfolioSnapshot": {
                "type": "object",
                "required": ["cash", "position", "equity", "exposure", "status"],
                "properties": {
                    "cash": {"type": "number"},
                    "position": {"type": "number"},
                    "equity": {"type": "number"},
                    "exposure": {"type": "number"},
                    "status": {"type": "string", "enum": ["active", "failed", "liquidated"]},
                },
            },
            "DecideRequest": {
                "type": "object",
                "required": ["tick", "market", "portfolio"],
                "properties": {
                    "tick": {"type": "integer", "minimum": 0},
                    "market": {"$ref": "#/components/schemas/MarketState"},
                    "portfolio": {"$ref": "#/components/schemas/PortfolioSnapshot"},
                },
            },
            "DecideResponse": {
                "type": "object",
                "required": ["action", "confidence", "size", "reason"],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["buy", "sell", "hold", "reduce_exposure"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "size": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}


CURL_EXAMPLE = """curl -X POST "https://your-agent.example.com/decide" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -d '{
    "tick": 0,
    "market": {
      "current_price": 100.0,
      "liquidity": 900.0,
      "volatility": 0.08,
      "market_sentiment": 0.05,
      "total_volume": 120.0
    },
    "portfolio": {
      "cash": 1000.0,
      "position": 0.0,
      "equity": 1000.0,
      "exposure": 0.0,
      "status": "active"
    }
  }'"""


PYTHON_EXAMPLE = '''import requests

response = requests.post(
    "https://your-agent.example.com/decide",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "tick": 0,
        "market": {
            "current_price": 100.0,
            "liquidity": 900.0,
            "volatility": 0.08,
            "market_sentiment": 0.05,
            "total_volume": 120.0,
        },
        "portfolio": {
            "cash": 1000.0,
            "position": 0.0,
            "equity": 1000.0,
            "exposure": 0.0,
            "status": "active",
        },
    },
    timeout=5,
)
response.raise_for_status()
decision = response.json()
print(decision)'''


FASTAPI_TEMPLATE = '''from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="My DUAT Agent")


class Market(BaseModel):
    current_price: float
    liquidity: float
    volatility: float
    market_sentiment: float
    total_volume: float


class Portfolio(BaseModel):
    cash: float
    position: float
    equity: float
    exposure: float
    status: str


class DecideRequest(BaseModel):
    tick: int
    market: Market
    portfolio: Portfolio


class DecideResponse(BaseModel):
    action: str = Field(pattern="^(buy|sell|hold|reduce_exposure)$")
    confidence: float = Field(ge=0, le=1)
    size: float = Field(ge=0, le=1)
    reason: str


@app.post("/decide", response_model=DecideResponse)
def decide(body: DecideRequest) -> DecideResponse:
    if body.market.volatility > 0.15:
        return DecideResponse(
            action="reduce_exposure",
            confidence=0.8,
            size=0.5,
            reason="High volatility — trimming risk.",
        )
    return DecideResponse(
        action="hold",
        confidence=0.6,
        size=1.0,
        reason="Conditions stable.",
    )'''


EXPRESS_TEMPLATE = '''const express = require("express");

const app = express();
app.use(express.json());

app.post("/decide", (req, res) => {
  const { tick, market, portfolio } = req.body;

  if (market.volatility > 0.15) {
    return res.json({
      action: "reduce_exposure",
      confidence: 0.8,
      size: 0.5,
      reason: "High volatility — trimming risk.",
    });
  }

  return res.json({
    action: "hold",
    confidence: 0.6,
    size: 1.0,
    reason: "Conditions stable.",
  });
});

app.listen(3000, () => console.log("Agent listening on :3000/decide"));'''


def integration_docs_payload() -> Dict[str, Any]:
    return {
        "openapi": OPENAPI_SPEC,
        "openapi_json": json.dumps(OPENAPI_SPEC, indent=2),
        "curl_example": CURL_EXAMPLE,
        "python_example": PYTHON_EXAMPLE,
        "fastapi_template": FASTAPI_TEMPLATE,
        "express_template": EXPRESS_TEMPLATE,
    }
