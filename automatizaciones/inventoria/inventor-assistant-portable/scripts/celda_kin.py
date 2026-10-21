"""Cinemática simple del KUKA KR 140 R3200-2 PA (modelo del proyecto ADECO2) para ubicar eslabones y gripper.

Coordenadas del ensamble del robot (mm, Y arriba):
  A1: eje Y por el origen (gira V02..V05)
  A2: eje Z por (330, 645)          (gira V03..V05)
  A3: eje Z por (338.02, 1994.98)   (gira V04..V05)
  Muñeca: eje Z por (1291.82, 1179.32); la brida (V05) se mantiene horizontal mirando hacia abajo (paralelogramo).
  A6: el gripper gira alrededor del eje vertical de la brida.
Matrices 4x4 en listas (traslación en mm).
"""
import math

A2 = (330.0, 645.0)
A3 = (338.02, 1994.98)
W = (1291.82, 1179.32)


def mmul(P, Q):
    return [[sum(P[i][k] * Q[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inv_rt(M):
    """Inversa de una matriz de rotación + traslación."""
    R = [[M[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(R[i][k] * M[k][3] for k in range(3)) for i in range(3)]
    return [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0, 0, 0, 1]]


def tr(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def rot_z(deg, p=(0.0, 0.0)):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    R = [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return mmul(mmul(tr(p[0], p[1], 0), R), tr(-p[0], -p[1], 0))


def rot_y(deg, p=(0.0, 0.0)):
    """Giro alrededor de un eje vertical (Y) que pasa por (x=p[0], z=p[1])."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    R = [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]
    return mmul(mmul(tr(p[0], 0, p[1]), R), tr(-p[0], 0, -p[1]))


def poses(cfg, q1=0.0, q2=0.0, q3=0.0, q6=0.0):
    """Matrices (coordenadas de la celda) de V02..V05 y del gripper para los ángulos dados (grados)."""
    T = cfg["T_robot"]                       # robot -> celda
    phi0 = cfg["phi0"]
    T1 = rot_y(q1)
    T2 = mmul(T1, rot_z(q2, A2))
    T3 = mmul(T2, rot_z(q3, A3))
    T5 = mmul(T3, rot_z(phi0 - q2 - q3, W))
    out = {
        "V02": mmul(T, mmul(T1, cfg["M"]["V02"])),
        "V03": mmul(T, mmul(T2, cfg["M"]["V03"])),
        "V04": mmul(T, mmul(T3, cfg["M"]["V04"])),
        "V05": mmul(T, mmul(T5, cfg["M"]["V05"])),
    }
    F = cfg["brida_robot_q0"]                # centro de la brida (q = 0, muñeca corregida)
    Tg = mmul(mmul(T5, inv_rt(rot_z(phi0, W))), rot_y(q6, (F[0], F[2])))
    out["gripper"] = mmul(T, mmul(Tg, cfg["M_gripper_q0"]))
    return out
