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
WINNING_SCORE = 8

# Physics scale  (1 px ≈ 1 000 000 km  →  just for flavour; all sim in px)
G_CONSTANT      = 100_000   # gravitational constant (tuned for fun)
BLACK_HOLE_MASS = 1.0      # relative mass multiplier
BH_MAX_ACCEL    = 1.5      # cap gravity acceleration per frame (prevents inescapable pull)
BH_SPEED_REDUCTION = 0.5   # ball speed multiplier on black hole exit (0.1 = very slow, 1.0 = no change)

# Asteroid belt
BELT_SCROLL_SPEED  = {"easy": 0.5, "medium": 1.5, "hard": 3.0, None: 1.0}  # px/frame per difficulty
BELT_DENSITY_CYCLE = 600   # frames for one full dense→sparse→dense cycle (~10 seconds)
BELT_PUNCH_SPEED   = 9.0   # ball speed threshold to punch through asteroids instead of bouncing

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


#menu and buttons
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
        self.btn_1p = Button(cx, HEIGHT//2 - 20,  320, 60, "story mode",  (0, 200, 255))
        self.btn_2p = Button(cx, HEIGHT//2 + 70,  320, 60, "arcade mode", (255, 100, 50))
        # Difficulty screen buttons
        self.btn_easy   = Button(cx, HEIGHT//2 - 80, 320, 60, "Earthling",   (0, 200, 100))
        self.btn_medium = Button(cx, HEIGHT//2,      320, 60, "Space Ranger", (255, 180, 0))
        self.btn_hard   = Button(cx, HEIGHT//2 + 80, 320, 60, "warp Admiral",   (255, 50,  50))
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
    pygame.display.set_caption("Cosmic Pong")
    Menu(screen).run()
