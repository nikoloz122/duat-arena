# SOLID Guidance

DUAT Arena should stay readable before it becomes abstract. Use SOLID principles as practical guardrails, not as a reason to create extra layers.

## Single Responsibility

Keep simulation, agents, scenarios, replay parsing, and API routing separate enough that each file has a clear job.

## Open / Closed

Add new agents and scenarios by creating small modules that follow the existing contracts. Avoid changing the engine for every new behavior unless the simulation model itself needs to evolve.

## Liskov Substitution

Any `TradingAgent` should be usable by the simulation engine without special handling. Any `ChaosScenario` should be able to apply deterministic market effects.

## Interface Segregation

Keep contracts small. Agents should decide actions; scenarios should mutate market state; replay utilities should read and write replay files.

## Dependency Inversion

The engine should depend on simple agent and scenario contracts, not specific implementations. Keep dependency injection lightweight and explicit.

## MVP Rule

If a SOLID-inspired abstraction does not make the current simulation, replay, or analysis loop easier to understand, do not add it yet.
