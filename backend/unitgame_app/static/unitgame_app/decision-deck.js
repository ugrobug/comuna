const MIN_FIXED_COSTS = 20;

// Owns the remaining decisions and checks eligibility against the current month.
export class DecisionDeck {
  #source;
  #remaining;
  #shuffle;
  #resolveEffects;

  constructor(cards, shuffle, resolveEffects) {
    this.#source = cards.slice();
    this.#shuffle = shuffle;
    this.#resolveEffects = resolveEffects;
    this.reset();
  }

  reset() {
    this.#remaining = this.#shuffle(this.#source.slice());
  }

  #isAvailable(card, state) {
    if (state.fixed >= MIN_FIXED_COSTS) return true;
    return ![card.left, card.right].some(choice => {
      const effects = this.#resolveEffects(choice, state);
      return effects.instant.fixed < 0 || effects.after.fixed < 0;
    });
  }

  draw(state) {
    // At most two scans: the current queue, then a fresh cycle. No retry loop.
    for (let cycle = 0; cycle < 2; cycle += 1) {
      const index = this.#remaining.findIndex(card => this.#isAvailable(card, state));
      if (index !== -1) return this.#remaining.splice(index, 1)[0];
      if (cycle === 0) this.reset();
    }
    // The game deck must contain at least one decision available at zero costs.
    throw new Error('No eligible decisions in the game deck');
  }
}
