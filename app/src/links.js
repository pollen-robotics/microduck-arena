// Every address that leaves the arena, in one place. The strip under a race
// page and the band under the front page both point at these, and an address
// that lives in two files is an address that goes stale in one of them.

export const FLOCK = "https://discord.com/invite/pollen-community-519098054377340948";
// Tagged, so the store's own analytics can tell which sales the arena brought.
export const STORE = "https://store.pollen-robotics.com/products/microduck?utm_source=microduck-arena&utm_medium=referral";
export const POLLEN = "https://pollen-robotics.com/";
export const MICRODUCK = "https://pollen-robotics.com/microduck/";
// Where a policy is trained, which is what "create policies" means: the RL
// repo, not this Space's own source.
export const MICRODUCK_RL = "https://github.com/pollen-robotics/microduck_rl";
