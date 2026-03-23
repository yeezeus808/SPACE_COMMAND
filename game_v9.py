"""
╔══════════════════════════════════════════════════════╗
║           COSMIC PONG  –  Space Ping Pong            ║
║  Physics: Dynamics · Collisions · Orbital Mechanics  ║
╚══════════════════════════════════════════════════════╝

Controls
  Player 1 (left)  : W / S
  Player 2 (right) : UP / DOWN  (or AI in single player)
  Pause            : P
  Restart          : R (after game over)
  Main Menu        : M (after game over)

VERSION 6 - Start screen UI + difficulty selection
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
G_CONSTANT      = 55_000   # gravitational constant (tuned for fun)
BLACK_HOLE_MASS = 1.0      # relative mass multiplier
BH_MAX_ACCEL    = 2.5      # cap gravity acceleration per frame (prevents inescapable pull)
BH_SPEED_REDUCTION = 0.9   # ball speed multiplier on black hole exit (0.1 = very slow, 1.0 = no change)

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
    def __init__(self, x, y, ring_colour):
        self.x = x
        self.y = y
        self.mass = G_CONSTANT * BLACK_HOLE_MASS
        self.radius = 22
        self.angle  = 0
        self.ring_colour = ring_colour  # each portal has its own colour
        self.partner = None             # linked wormhole exit, set after creation

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
        r, g, b = self.ring_colour
        for i, (r_offset, alpha) in enumerate([(38,60),(50,40),(62,25)]):
            ring_surf = pygame.Surface((r_offset*2+4, r_offset*2+4), pygame.SRCALPHA)
            a_col = (r, g + i*20, b, alpha)
            pygame.draw.ellipse(ring_surf, a_col,
                                (0, r_offset//2, r_offset*2+4, r_offset+4), 3)
            rot = pygame.transform.rotate(ring_surf, self.angle + i*30)
            surf.blit(rot, (self.x - rot.get_width()//2, self.y - rot.get_height()//2))
        draw_glow(surf, self.ring_colour, (self.x, self.y), 30, alpha=90)
        pygame.draw.circle(surf, C_BH_CORE, (self.x, self.y), self.radius)
        pygame.draw.circle(surf, self.ring_colour, (self.x, self.y), self.radius, 2)

    def swallowed(self, ball):
        dist = math.hypot(self.x - ball.x, self.y - ball.y)
        return dist < self.radius + ball.radius

    def eject_ball(self, ball):
        """Wormhole — eject ball out of the partner black hole toward the correct player."""
        exit_hole = self.partner if self.partner else self
        eject_dist = exit_hole.radius + ball.radius + 60
        # If exit hole is on the left side, eject leftward toward Player 1
        # If exit hole is on the right side, eject rightward toward Player 2
        direction = -1 if exit_hole.x < WIDTH // 2 else 1
        ball.x = exit_hole.x + direction * eject_dist
        ball.y = exit_hole.y + random.randint(-60, 60)
        exit_speed = max(6.0, math.hypot(ball.vx, ball.vy)) * BH_SPEED_REDUCTION
        ball.vx = direction * exit_speed
        ball.vy = random.uniform(-2.0, 2.0)
        ball.trail = []


class Paddle:
    W, H = 14, 90

    def __init__(self, x, up_key, down_key, colour):
        self.x      = x
        self.y      = HEIGHT // 2
        self.speed  = 14
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
    def __init__(self, screen, two_player=True, difficulty=None):
        self.screen     = screen
        self.two_player = two_player
        self.difficulty = difficulty  # "easy" | "medium" | "hard" | None
        self.clock  = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("arial", 72, bold=True)
        self.font_md = pygame.font.SysFont("arial", 28, bold=True)
        self.font_sm = pygame.font.SysFont("arial", 18)
        self.stars   = Stars()
        self.belt    = AsteroidBelt()
        # Two wormhole-connected black holes, one per side
        self.bh_l = BlackHole(WIDTH // 4,     HEIGHT // 2, (60, 180, 255))  # left  — blue
        self.bh_r = BlackHole(WIDTH * 3 // 4, HEIGHT // 2, (180, 60, 255))  # right — purple
        self.bh_l.partner = self.bh_r
        self.bh_r.partner = self.bh_l
        self.black_holes = [self.bh_l, self.bh_r]
        self.paddle_l = Paddle(40,  pygame.K_w, pygame.K_s,  C_PADDLE_L)
        self.paddle_r = Paddle(WIDTH-40, pygame.K_UP, pygame.K_DOWN, C_PADDLE_R)
        self.ball    = Ball()
        self.paused  = False
        self.game_over = False
        self.winner  = ""
        self.particles = []
        self.slow_timer = 0  # tracks how long ball has been moving slowly (in frames)

        # ── Dev mode flags ──
        self.dev_mode      = False   # master toggle
        self.dev_hitboxes  = False   # show collision zones
        self.dev_gravity   = True    # black hole gravity on/off
        self.dev_invincible= False   # paddles never score
        self.font_dev      = pygame.font.SysFont("consolas", 16)

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

    def run(self, menu=None):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                    if event.key == pygame.K_r and self.game_over:
                        Game(self.screen, self.two_player, self.difficulty).run(menu)
                        return
                    if event.key == pygame.K_m and self.game_over:
                        if menu:
                            menu.run()
                        return
                    # ── Dev mode keys ──
                    if event.key == pygame.K_F1:
                        self.dev_mode     = not self.dev_mode
                    if self.dev_mode:
                        if event.key == pygame.K_F2:
                            self.dev_hitboxes   = not self.dev_hitboxes
                        if event.key == pygame.K_F3:
                            self.dev_gravity    = not self.dev_gravity
                        if event.key == pygame.K_F4:
                            self.dev_invincible = not self.dev_invincible
                        if event.key == pygame.K_n:
                            self.ball.next_planet(); self.ball.reset()
                        if event.key == pygame.K_b:
                            self.ball.planet_idx = max(0, self.ball.planet_idx - 2)
                            self.ball.next_planet(); self.ball.reset()
                        if event.key == pygame.K_KP_PLUS or event.key == pygame.K_EQUALS:
                            spd = math.hypot(self.ball.vx, self.ball.vy)
                            factor = (spd + 1.0) / max(spd, 0.1)
                            self.ball.vx *= factor; self.ball.vy *= factor
                        if event.key == pygame.K_KP_MINUS or event.key == pygame.K_MINUS:
                            spd = math.hypot(self.ball.vx, self.ball.vy)
                            factor = max(spd - 1.0, 1.0) / max(spd, 0.1)
                            self.ball.vx *= factor; self.ball.vy *= factor
                # Click to teleport ball in dev mode
                if event.type == pygame.MOUSEBUTTONDOWN and self.dev_mode:
                    self.ball.x = event.pos[0]
                    self.ball.y = event.pos[1]
                    self.ball.trail = []
            if not self.paused and not self.game_over:
                self.update()
            self.draw()
            pygame.display.flip()

    def update(self):
        keys = pygame.key.get_pressed()
        self.paddle_l.update(keys)
        self.paddle_r.update(keys)
        # Gravity + wormhole for both black holes
        if self.dev_gravity:
            for bh in self.black_holes:
                bh.apply_gravity(self.ball)
        self.ball.update()
        self.update_particles()
        for bh in self.black_holes:
            if bh.swallowed(self.ball):
                self.spawn_particles(bh.x, bh.y, bh.ring_colour, 25)
                bh.eject_ball(self.ball)
                break
        self.belt.collides_with_ball(self.ball)
        paddle_ball_collision(self.paddle_l, self.ball)
        paddle_ball_collision(self.paddle_r, self.ball)

        # Orbit escape — only kick if ball has been slow for 2.5 seconds (150 frames at 60fps)
        speed = math.hypot(self.ball.vx, self.ball.vy)
        if speed < 3.0:
            self.slow_timer += 1
        else:
            self.slow_timer = 0
        if self.slow_timer >= 150:
            angle = random.uniform(0, 2 * math.pi)
            self.ball.vx += math.cos(angle) * 4.0
            self.ball.vy += math.sin(angle) * 4.0
            self.slow_timer = 0

        # Scoring — skip if invincible mode on
        if not self.dev_invincible:
            if self.ball.x + self.ball.radius < 0:
                self.score_point(self.paddle_r, direction=1)
            if self.ball.x - self.ball.radius > WIDTH:
                self.score_point(self.paddle_l, direction=-1)
        else:
            # Bounce off walls instead of scoring
            if self.ball.x - self.ball.radius < 0:
                self.ball.x  = self.ball.radius
                self.ball.vx = abs(self.ball.vx)
            if self.ball.x + self.ball.radius > WIDTH:
                self.ball.x  = WIDTH - self.ball.radius
                self.ball.vx = -abs(self.ball.vx)

    def draw(self):
        self.screen.fill(C_BG)
        self.stars.draw(self.screen)
        self.belt.draw(self.screen)
        for bh in self.black_holes:
            bh.draw(self.screen)
        self.paddle_l.draw(self.screen)
        self.paddle_r.draw(self.screen)
        self.ball.draw(self.screen)
        self.draw_particles()
        self.draw_hud()
        if self.dev_mode:
            self.draw_dev_overlay()
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
            t2 = self.font_md.render("R  — Play Again     M  — Main Menu", True, C_HUD)
            self.screen.blit(t1, (WIDTH//2 - t1.get_width()//2, HEIGHT//2 - 60))
            self.screen.blit(t2, (WIDTH//2 - t2.get_width()//2, HEIGHT//2 + 20))

    def draw_dev_overlay(self):
        """Draw dev mode panel and optional hitboxes."""
        # ── Hitboxes ──
        if self.dev_hitboxes:
            # Ball collision circle
            pygame.draw.circle(self.screen, (0, 255, 0),
                               (int(self.ball.x), int(self.ball.y)),
                               self.ball.radius, 2)
            # Paddle rectangles
            pygame.draw.rect(self.screen, (0, 255, 0), self.paddle_l.rect(), 2)
            pygame.draw.rect(self.screen, (0, 255, 0), self.paddle_r.rect(), 2)
            # Asteroid collision circles
            for a in self.belt.asteroids:
                pygame.draw.circle(self.screen, (255, 165, 0),
                                   (a["x"], a["y"]), a["r"], 2)
            # Black hole swallow zones
            for bh in self.black_holes:
                pygame.draw.circle(self.screen, (255, 0, 0),
                                   (bh.x, bh.y),
                                   bh.radius + self.ball.radius, 2)

        # ── Dev panel (top-right) ──
        panel_lines = [
            "── DEV MODE ──",
            f"F1  Dev mode  ON",
            f"F2  Hitboxes  {'ON' if self.dev_hitboxes else 'OFF'}",
            f"F3  Gravity   {'ON' if self.dev_gravity else 'OFF'}",
            f"F4  Invincible {'ON' if self.dev_invincible else 'OFF'}",
            f"N/B  Next/Prev planet",
            f"+/-  Speed adjust",
            f"Click  Teleport ball",
            f"──────────────",
            f"Planet : {self.ball.name}",
            f"Speed  : {math.hypot(self.ball.vx, self.ball.vy):.2f} px/s",
            f"vx     : {self.ball.vx:.2f}",
            f"vy     : {self.ball.vy:.2f}",
            f"Mass   : {self.ball.mass_rel:.3f} M⊕",
        ]
        pad = 10
        line_h = 20
        panel_w = 220
        panel_h = len(panel_lines) * line_h + pad * 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        self.screen.blit(panel, (WIDTH - panel_w - 8, 8))
        for i, line in enumerate(panel_lines):
            col = (0, 255, 100) if line.startswith("──") else (180, 255, 180)
            t = self.font_dev.render(line, True, col)
            self.screen.blit(t, (WIDTH - panel_w - 8 + pad, 8 + pad + i * line_h))

        # Dev mode badge (top centre)
        badge = self.font_dev.render("⚙  DEV MODE  —  F1 to exit", True, (255, 220, 0))
        self.screen.blit(badge, (WIDTH//2 - badge.get_width()//2, HEIGHT - 50))



class Button:
    """A glowing space-themed button."""
    def __init__(self, x, y, w, h, text, colour):
        self.rect   = pygame.Rect(x - w//2, y - h//2, w, h)
        self.text   = text
        self.colour = colour
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def clicked(self, mouse_pos, mouse_click):
        return self.rect.collidepoint(mouse_pos) and mouse_click

    def draw(self, surf, font):
        # Glow when hovered
        if self.hovered:
            draw_glow(surf, self.colour, self.rect.center, 36, alpha=80)
        # Button background
        bg_alpha = 180 if self.hovered else 100
        bg = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        bg.fill((*self.colour, bg_alpha))
        surf.blit(bg, self.rect.topleft)
        # Border
        border_col = C_WHITE if self.hovered else self.colour
        pygame.draw.rect(surf, border_col, self.rect, 2, border_radius=8)
        # Label
        label = font.render(self.text, True, C_WHITE)
        surf.blit(label, (self.rect.centerx - label.get_width()//2,
                          self.rect.centery - label.get_height()//2))


class Menu:
    """Start screen and difficulty selection screen."""

    SCREEN_MAIN       = "main"
    SCREEN_DIFFICULTY = "difficulty"

    def __init__(self, screen):
        self.screen   = screen
        self.stars    = Stars()
        self.clock    = pygame.time.Clock()
        self.font_xl  = pygame.font.SysFont("arial", 80, bold=True)
        self.font_lg  = pygame.font.SysFont("arial", 36, bold=True)
        self.font_sm  = pygame.font.SysFont("arial", 20)
        self.current  = self.SCREEN_MAIN
        self._build_buttons()

    def _build_buttons(self):
        cx = WIDTH // 2
        # Main screen buttons
        self.btn_1p = Button(cx, HEIGHT//2 - 20,  320, 60, "1  Player",  (0, 200, 255))
        self.btn_2p = Button(cx, HEIGHT//2 + 70,  320, 60, "2  Players", (255, 100, 50))
        # Difficulty screen buttons
        self.btn_easy   = Button(cx, HEIGHT//2 - 80, 320, 60, "Easy",   (0, 200, 100))
        self.btn_medium = Button(cx, HEIGHT//2,      320, 60, "Medium", (255, 180, 0))
        self.btn_hard   = Button(cx, HEIGHT//2 + 80, 320, 60, "Hard",   (255, 50,  50))
        self.btn_back   = Button(cx, HEIGHT//2 + 180, 220, 45, "← Back", (120, 120, 160))

    def run(self):
        while True:
            self.clock.tick(FPS)
            mouse_pos   = pygame.mouse.get_pos()
            mouse_click = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_click = True
                if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                    # Launch dev mode directly from menu
                    g = Game(self.screen, two_player=True, difficulty=None)
                    g.dev_mode = True
                    g.run(self)
                    return

            if self.current == self.SCREEN_MAIN:
                self._handle_main(mouse_pos, mouse_click)
                self._draw_main(mouse_pos)
            else:
                self._handle_difficulty(mouse_pos, mouse_click)
                self._draw_difficulty(mouse_pos)

            pygame.display.flip()

    def _handle_main(self, mp, click):
        self.btn_1p.update(mp)
        self.btn_2p.update(mp)
        if self.btn_1p.clicked(mp, click):
            self.current = self.SCREEN_DIFFICULTY
        if self.btn_2p.clicked(mp, click):
            self._launch(two_player=True)

    def _handle_difficulty(self, mp, click):
        for btn in [self.btn_easy, self.btn_medium, self.btn_hard, self.btn_back]:
            btn.update(mp)
        if self.btn_easy.clicked(mp, click):
            self._launch(two_player=False, difficulty="easy")
        if self.btn_medium.clicked(mp, click):
            self._launch(two_player=False, difficulty="medium")
        if self.btn_hard.clicked(mp, click):
            self._launch(two_player=False, difficulty="hard")
        if self.btn_back.clicked(mp, click):
            self.current = self.SCREEN_MAIN

    def _launch(self, two_player, difficulty=None):
        Game(self.screen, two_player=two_player, difficulty=difficulty).run(self)

    # ── Drawing ──

    def _draw_stars(self):
        self.screen.fill(C_BG)
        self.stars.draw(self.screen)

    def _draw_title(self):
        # Title glow
        draw_glow(self.screen, (0, 150, 255), (WIDTH//2, 130), 60, alpha=60)
        title = self.font_xl.render("COSMIC  PONG", True, C_WHITE)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))
        sub = self.font_sm.render("Physics-powered space ping pong", True, C_HUD)
        self.screen.blit(sub, (WIDTH//2 - sub.get_width()//2, 175))

    def _draw_main(self, mp):
        self._draw_stars()
        self._draw_title()
        prompt = self.font_lg.render("Select Mode", True, C_HUD)
        self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2 - 100))
        self.btn_1p.draw(self.screen, self.font_lg)
        self.btn_2p.draw(self.screen, self.font_lg)
        hint = self.font_sm.render("P1: W / S     P2: ↑ / ↓", True, (80, 80, 120))
        self.screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 40))
        dev_hint = self.font_sm.render("Hold D to enter Dev Mode", True, (60, 60, 80))
        self.screen.blit(dev_hint, (WIDTH//2 - dev_hint.get_width()//2, HEIGHT - 18))

    def _draw_difficulty(self, mp):
        self._draw_stars()
        self._draw_title()
        prompt = self.font_lg.render("Select Difficulty", True, C_HUD)
        self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2 - 170))
        # Descriptions
        descs = [
            (self.btn_easy,   "AI is slow and misses often"),
            (self.btn_medium, "AI has reaction delay, misses sometimes"),
            (self.btn_hard,   "AI is fast and rarely misses"),
        ]
        for btn, desc in descs:
            btn.draw(self.screen, self.font_lg)
            if btn.hovered:
                d = self.font_sm.render(desc, True, (180, 180, 220))
                self.screen.blit(d, (WIDTH//2 - d.get_width()//2, btn.rect.bottom + 6))
        self.btn_back.draw(self.screen, self.font_sm)


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("🪐 Cosmic Pong")
    Menu(screen).run()
