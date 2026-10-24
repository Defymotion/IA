"""Choques de los eslabones del robot (nube de puntos de la superficie real, desde el STL) contra cajas fijas."""
import json

import numpy as np

LINK_PIEZA = {"V01": "KR_140_R3200-2_PA_V01.ipt", "V02": "KR_140_R3200-2_PA_V02.ipt", "V03": "KR_140_R3200-2_PA_V03.ipt",
              "V04": "KR_140_R3200-2_PA_V04.ipt", "V05": "KR_140_R3200-2_PA_V05.ipt"}


class Brazo:
    def __init__(self, ruta_puntos):
        d = json.load(open(ruta_puntos))
        self.P = {k: np.array(d[v]["puntos"], dtype=float) for k, v in LINK_PIEZA.items()}

    def puntos_mundo(self, poses, links=("V02", "V03", "V04", "V05")):
        out = []
        for k in links:
            M = np.array(poses[k], dtype=float)
            out.append(self.P[k] @ M[:3, :3].T + M[:3, 3])
        return out

    @staticmethod
    def choques(pts_list, cajas, h=10.0):
        """Lista de (índice de caja, eslabón, penetración aproximada) de las cajas tocadas."""
        res = []
        if not len(cajas):
            return res
        C = np.array(cajas, dtype=float)
        lo, hi = C[:, :3] - h, C[:, 3:] + h
        for li, P in enumerate(pts_list):
            pmin, pmax = P.min(0), P.max(0)
            cand = np.where(np.all(hi > pmin, axis=1) & np.all(lo < pmax, axis=1))[0]
            for ci in cand:
                m = np.all(P > lo[ci], axis=1) & np.all(P < hi[ci], axis=1)
                if m.any():
                    Q = P[m]
                    pen = float(np.min(np.minimum(Q - lo[ci], hi[ci] - Q).min(1)))
                    res.append((int(ci), li, round(pen, 1), int(m.sum())))
        return res
