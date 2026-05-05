"""
╔══════════════════════════════════════════════════════╗
║           COSMIC PONG  –  Space Ping Pong            ║
║  Physics: Dynamics · Collisions · Orbital Mechanics  ║
╚══════════════════════════════════════════════════════╝

Controls
  Player 1 (left)  : W / S
  Player 2 (right) : UP / DOWN
  Pause            : P
  Restart          : R (after game over)

VERSION 4 - Black hole weakened + asteroid stuck fix + Mercury black hole fix
"""

import pygame
import math
import random
import sys

# ── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1200, 700
FPS = 60
WINNING_SCORE = 7

# Physics scale  (1 px ≈ 1 000 000 km  →  just for flavour; all sim in px)
G_CONSTANT   = 55_000    # gravitational constant (tuned for fun)
BLACK_HOLE_MASS = 1.0    # relative mass multiplier
BH_MAX_ACCEL = 2.5       # cap gravity acceleration per frame (prevents inescapable pull)

# Colours
C_BG         = (5,  5, 20)
C_STAR       = (255, 255, 255)
C_HUD        = (200, 200, 255)
C_NET        = (180, 120,  40)
C_BH_CORE    = (0,   0,   0)
C_BH_RING    = (180,  60, 255)
C_WHITE      = (255, 255, 255)
C_PADDLE_L   = (0,  200, 255)
C_PADDLE_R   = (255, 100,  50)

# ── Planet data ──────────────────────────────────────────────────────────────
PLANETS = [
    # name,       colour,            radius, mass(kg rel), fun-fact
    ("Mercury", (169, 169, 169),      8,   0.055, "Smallest planet"),
    ("Venus",   (255, 198,  93),     14,   0.815, "Hottest planet"),
    ("Earth",   ( 70, 130, 180),     14,   1.000, "Our home"),
    ("Mars",    (188,  74,  60),     11,   0.107, "The Red Planet"),
    ("Jupiter", (201, 144,  57),     28,   317.8, "Largest planet"),
    ("Saturn",  (210, 180, 140),     24,   95.16, "Has rings!"),
    ("Uranus",  (173, 216, 230),     20,   14.54, "Rotates sideways"),
    ("Neptune", ( 63,  84, 186),     18,   17.15, "Windiest planet"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def draw_glow(surf, colour, pos, radius, alpha=80):
    glow = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
    for r in range(radius*2, 0, -4):
        a = int(alpha * (1 - r / (radius*2)))
        pygame.draw.circle(glow, (*colour, a), (radius*2, radius*2), r)
    surf.blit(glow, (pos[0]-radius*2, pos[1]-radius*2))


# ── Classes ──────────────────────────────────────────────────────────────────

class Stars:
    def __init__(self, n=150):
        self.positions = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(n)]
        self.sizes     = [random.choice([1, 1, 1, 2]) for _ in range(n)]

    def draw(self, surf):
        for (x, y), s in zip(self.positions, self.sizes):
            pygame.draw.circle(surf, C_STAR, (x, y), s)


class AsteroidBelt:
    """Decorative + collision net in the centre."""
    def __init__(self):
        self.asteroids = []
        cx = WIDTH // 2
        for _ in range(28):
            x = cx + random.randint(-18, 18)
            y = random.randint(40, HEIGHT - 40)
            r = random.randint(5, 14)
            shade = random.randint(110, 180)
            self.asteroids.append({"x": x, "y": y, "r": r,
                                   "col": (shade, shade//2, shade//3)})

    def draw(self, surf):
        for a in self.asteroids:
            pygame.draw.circle(surf, a["col"], (a["x"], a["y"]), a["r"])
            pygame.draw.circle(surf, (80, 50, 30), (a["x"], a["y"]), a["r"], 1)

    def collides_with_ball(self, ball):
        """Return True (and bounce ball) if ball hits any asteroid."""
        hit = False
        for _ in range(3):  # up to 3 resolution passes to prevent tunnelling/sticking
            for a in self.asteroids:
                dx = ball.x - a["x"]
                dy = ball.y - a["y"]
                dist = math.hypot(dx, dy)
                min_dist = ball.radius + a["r"]
                if dist < min_dist and dist > 0:
                    nx, ny = dx/dist, dy/dist
                    # ── Conservation of momentum (elastic, asteroid treated as immovable wall) ──
                    dot = ball.vx * nx + ball.vy * ny
                    if dot < 0:  # only reflect if moving toward asteroid
                        ball.vx -= 2 * dot * nx
                        ball.vy -= 2 * dot * ny
                    # Springy push — bigger overlap = stronger ejection force
                    overlap = min_dist - dist
                    spring_force = 2.0 + overlap * 0.8  # scales with how deep the planet is buried
                    ball.x += nx * (overlap + spring_force)
                    ball.y += ny * (overlap + spring_force)
                    # Ensure minimum exit speed so ball never gets stuck
                    speed = math.hypot(ball.vx, ball.vy)
                    if speed < 4.0:
                        ball.vx = nx * 4.0
                        ball.vy = ny * 4.0
                    hit = True
        return hit


class BlackHole:
    def __init__(self):
        self.x = WIDTH * 3 // 4
        self.y = HEIGHT // 2
        self.mass = G_CONSTANT * BLACK_HOLE_MASS
        self.radius = 22
        self.angle  = 0

    def apply_gravity(self, ball):
        """Newton's law of gravitation:  F = G*M / r²  (applied as acceleration)."""
        dx = self.x - ball.x
        dy = self.y - ball.y
        dist_sq = dx*dx + dy*dy
        dist    = math.sqrt(dist_sq)
        if dist < 5:
            return
        accel = min(self.mass / dist_sq, BH_MAX_ACCEL)  # capped so ball can escape
        ball.vx += accel * (dx / dist)
        ball.vy += accel * (dy / dist)

    def draw(self, surf):
        self.angle = (self.angle + 1.5) % 360
        for i, (r_offset, alpha) in enumerate([(38,60),(50,40),(62,25)]):
            ring_surf = pygame.Surface((r_offset*2+4, r_offset*2+4), pygame.SRCALPHA)
            a_col = (180, 60+i*20, 255, alpha)
            pygame.draw.ellipse(ring_surf, a_col,
                                (0, r_offset//2, r_offset*2+4, r_offset+4), 3)
            rot = pygame.transform.rotate(ring_surf, self.angle + i*30)
            surf.blit(rot, (self.x - rot.get_width()//2, self.y - rot.get_height()//2))
        draw_glow(surf, (120, 0, 200), (self.x, self.y), 30, alpha=90)
        pygame.draw.circle(surf, C_BH_CORE, (self.x, self.y), self.radius)
        pygame.draw.circle(surf, C_BH_RING, (self.x, self.y), self.radius, 2)

    def swallowed(self, ball):
        dist = math.hypot(self.x - ball.x, self.y - ball.y)
        return dist < self.radius + ball.radius  # accounts for any planet size

    def eject_ball(self, ball):
        """Teleport ball safely away from the black hole with enough speed to escape."""
        eject_dist = self.radius + ball.radius + 60
        ball.x = self.x - eject_dist
        ball.y = self.y + random.randint(-80, 80)
        ball.vx = -max(6.0, math.hypot(ball.vx, ball.vy))
        ball.vy = random.uniform(-2.0, 2.0)
        ball.trail = []


class Paddle:
    W, H = 14, 90

    def __init__(self, x, up_key, down_key, colour):
        self.x      = x
        self.y      = HEIGHT // 2
        self.speed  = 7
        self.up_key = up_key
        self.dn_key = down_key
        self.colour = colour
        self.score  = 0

    def update(self, keys):
        if keys[self.up_key]:
            self.y -= self.speed
        if keys[self.dn_key]:
            self.y += self.speed
        half = self.H // 2
        self.y = clamp(self.y, half, HEIGHT - half)

    def rect(self):
        return pygame.Rect(self.x - self.W//2,
                           self.y - self.H//2,
                           self.W, self.H)

    def draw(self, surf):
        r = self.rect()
        draw_glow(surf, self.colour, r.center, 20, alpha=60)
        pygame.draw.rect(surf, self.colour, r, border_radius=7)
        pygame.draw.rect(surf, C_WHITE, r, 2, border_radius=7)


class Ball:
    BASE_SPEED = 5.5

    def __init__(self):
        self.planet_idx = 0
        self._load_planet()
        self.reset()

    def _load_planet(self):
        data = PLANETS[self.planet_idx % len(PLANETS)]
        self.name, self.colour, self.radius, self.mass_rel, self.fact = data

    def reset(self, direction=1):
        self.x  = WIDTH // 2
        self.y  = HEIGHT // 2
        angle   = random.uniform(-0.4, 0.4)
        speed   = self.BASE_SPEED / math.sqrt(self.mass_rel) if self.mass_rel > 0.1 else self.BASE_SPEED * 1.5
        speed   = clamp(speed, 3.0, 12.0)
        self.vx = direction * speed * math.cos(angle)
        self.vy = speed * math.sin(angle)
        self.trail = []

    def next_planet(self):
        self.planet_idx += 1
        self._load_planet()

    def update(self):
        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > 18:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        if self.y - self.radius <= 0:
            self.y  = self.radius
            self.vy = abs(self.vy)
        if self.y + self.radius >= HEIGHT:
            self.y  = HEIGHT - self.radius
            self.vy = -abs(self.vy)

    def draw(self, surf):
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(180 * i / len(self.trail)) if self.trail else 0
            r_t   = max(1, int(self.radius * i / len(self.trail)))
            ts = pygame.Surface((r_t*2+2, r_t*2+2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*self.colour, alpha), (r_t+1, r_t+1), r_t)
            surf.blit(ts, (tx - r_t, ty - r_t))
        draw_glow(surf, self.colour, (int(self.x), int(self.y)), self.radius+6, alpha=70)
        pygame.draw.circle(surf, self.colour, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, C_WHITE,     (int(self.x), int(self.y)), self.radius, 2)
        if self.name == "Saturn":
            cx, cy = int(self.x), int(self.y)
            ring_rect = pygame.Rect(cx - self.radius - 8, cy - 5,
                                    (self.radius + 8)*2, 10)
            pygame.draw.ellipse(surf, (210, 180, 140), ring_rect, 3)


def paddle_ball_collision(paddle, ball):
    pr = paddle.rect()
    expanded = pr.inflate(ball.radius*2, ball.radius*2)
    if not expanded.collidepoint(ball.x, ball.y):
        return False
    rel = (ball.y - paddle.y) / (paddle.H / 2)
    rel = clamp(rel, -1, 1)
    speed_factor = 1.0 / math.sqrt(ball.mass_rel) if ball.mass_rel > 0.1 else 1.5
    speed_factor = clamp(speed_factor, 0.5, 1.8)
    new_speed = math.hypot(ball.vx, ball.vy) * speed_factor
    new_speed  = clamp(new_speed, 3.0, 15.0)
    ball.vx = math.copysign(new_speed * math.cos(rel * 0.8), -ball.vx)
    ball.vy = new_speed * math.sin(rel * 0.8)
    if ball.vx > 0:
        ball.x = pr.right + ball.radius + 1
    else:
        ball.x = pr.left - ball.radius - 1
    return True


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("🪐 Cosmic Pong")
        self.clock  = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("arial", 72, bold=True)
        self.font_md = pygame.font.SysFont("arial", 28, bold=True)
        self.font_sm = pygame.font.SysFont("arial", 18)
        self.stars   = Stars()
        self.belt    = AsteroidBelt()
        self.bh      = BlackHole()
        self.paddle_l = Paddle(40,  pygame.K_w, pygame.K_s,  C_PADDLE_L)
        self.paddle_r = Paddle(WIDTH-40, pygame.K_UP, pygame.K_DOWN, C_PADDLE_R)
        self.ball    = Ball()
        self.paused  = False
        self.game_over = False
        self.winner  = ""
        self.particles = []
        self.slow_timer = 0  # tracks how long ball has been moving slowly (in frames)

    def spawn_particles(self, x, y, colour, n=12):
        for _ in range(n):
            angle = random.uniform(0, 2*math.pi)
            speed = random.uniform(1.5, 5)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle)*speed,
                "vy": math.sin(angle)*speed,
                "life": 30, "col": colour
            })

    def update_particles(self):
        for p in self.particles:
            p["x"] += p["vx"]; p["y"] += p["vy"]; p["life"] -= 1
        self.particles = [p for p in self.particles if p["life"] > 0]

    def draw_particles(self):
        for p in self.particles:
            alpha = int(255 * p["life"] / 30)
            r = max(1, p["life"] // 8)
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["col"], alpha), (r, r), r)
            self.screen.blit(s, (int(p["x"])-r, int(p["y"])-r))

    def draw_hud(self):
        score_l = self.font_lg.render(str(self.paddle_l.score), True, C_PADDLE_L)
        score_r = self.font_lg.render(str(self.paddle_r.score), True, C_PADDLE_R)
        self.screen.blit(score_l, (WIDTH//4 - score_l.get_width()//2, 10))
        self.screen.blit(score_r, (3*WIDTH//4 - score_r.get_width()//2, 10))
        info = f"🪐 {self.ball.name}  |  Mass: {self.ball.mass_rel:.3f} M⊕  |  {self.ball.fact}"
        t = self.font_sm.render(info, True, C_HUD)
        self.screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 28))
        speed = math.hypot(self.ball.vx, self.ball.vy)
        force = self.ball.mass_rel * speed
        lines = [f"v = {speed:.1f} px/s", f"F ∝ {force:.2f}  (m·|v|)", f"p = {self.ball.mass_rel * speed:.2f}  (m·v)"]
        for i, ln in enumerate(lines):
            t = self.font_sm.render(ln, True, (150, 200, 150))
            self.screen.blit(t, (8, HEIGHT//2 - 30 + i*20))
        ctrl = self.font_sm.render("P1: W/S     P2: ↑/↓     P: pause", True, (100,100,140))
        self.screen.blit(ctrl, (WIDTH//2 - ctrl.get_width()//2, 8))

    def score_point(self, scorer, direction):
        scorer.score += 1
        self.spawn_particles(self.ball.x, self.ball.y, self.ball.colour, 20)
        if scorer.score >= WINNING_SCORE:
            self.game_over = True
            self.winner = "Player 1" if scorer is self.paddle_l else "Player 2"
        else:
            self.ball.next_planet()
            self.ball.reset(direction=direction)

    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                    if event.key == pygame.K_r and self.game_over:
                        self.__init__(); return self.run()
            if not self.paused and not self.game_over:
                self.update()
            self.draw()
            pygame.display.flip()

    def update(self):
        keys = pygame.key.get_pressed()
        self.paddle_l.update(keys)
        self.paddle_r.update(keys)
        self.bh.apply_gravity(self.ball)
        self.ball.update()
        self.update_particles()
        if self.bh.swallowed(self.ball):
            self.spawn_particles(self.bh.x, self.bh.y, (180, 60, 255), 25)
            self.bh.eject_ball(self.ball)
        self.belt.collides_with_ball(self.ball)
        paddle_ball_collision(self.paddle_l, self.ball)
        paddle_ball_collision(self.paddle_r, self.ball)

        # Orbit escape — only kick if ball has been slow for 2.5 seconds (150 frames at 60fps)
        speed = math.hypot(self.ball.vx, self.ball.vy)
        if speed < 3.0:
            self.slow_timer += 1
        else:
            self.slow_timer = 0  # reset timer the moment ball speeds up again
        if self.slow_timer >= 150:
            angle = random.uniform(0, 2 * math.pi)
            self.ball.vx += math.cos(angle) * 4.0
            self.ball.vy += math.sin(angle) * 4.0
            self.slow_timer = 0
        if self.ball.x + self.ball.radius < 0:
            self.score_point(self.paddle_r, direction=1)
        if self.ball.x - self.ball.radius > WIDTH:
            self.score_point(self.paddle_l, direction=-1)

    def draw(self):
        self.screen.fill(C_BG)
        self.stars.draw(self.screen)
        self.belt.draw(self.screen)
        self.bh.draw(self.screen)
        self.paddle_l.draw(self.screen)
        self.paddle_r.draw(self.screen)
        self.ball.draw(self.screen)
        self.draw_particles()
        self.draw_hud()
        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 30, 140))
            self.screen.blit(overlay, (0, 0))
            t = self.font_lg.render("PAUSED", True, C_WHITE)
            self.screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 - 40))
        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 10, 170))
            self.screen.blit(overlay, (0, 0))
            t1 = self.font_lg.render(f"{self.winner} Wins!", True, C_WHITE)
            t2 = self.font_md.render("Press  R  to restart", True, C_HUD)
            self.screen.blit(t1, (WIDTH//2 - t1.get_width()//2, HEIGHT//2 - 60))
            self.screen.blit(t2, (WIDTH//2 - t2.get_width()//2, HEIGHT//2 + 20))

if __name__ == "__main__":
    Game().run()
