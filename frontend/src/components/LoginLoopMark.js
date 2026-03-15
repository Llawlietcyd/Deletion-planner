import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

function createEnvironmentTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 512;
  const context = canvas.getContext('2d');

  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = '#050505';
  context.fillRect(90, 0, 140, 512);
  context.fillRect(380, 0, 84, 512);
  context.fillRect(680, 0, 190, 512);
  context.fillRect(950, 0, 40, 512);
  context.fillRect(0, 104, 1024, 36);
  context.fillRect(0, 392, 1024, 56);

  const texture = new THREE.CanvasTexture(canvas);
  texture.mapping = THREE.EquirectangularReflectionMapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function getPathPoints(time, morphPhase, pointCount = 180) {
  const points = [];
  for (let index = 0; index <= pointCount; index += 1) {
    const t = index / pointCount;
    const angle = t * Math.PI * 2;

    const waveX = Math.sin(angle * 2 + time) * 2.8;
    const waveY = Math.cos(angle * 3 + time) * 1.95;
    const waveZ = Math.sin(angle - time) * 1.25;

    const knotScale = 1.42;
    const knotX = (Math.sin(angle) + 2 * Math.sin(2 * angle)) * knotScale;
    const knotY = (Math.cos(angle) - 2 * Math.cos(2 * angle)) * knotScale;
    const knotZ = -Math.sin(3 * angle) * knotScale;

    const easeMorph = morphPhase < 0.5
      ? 4 * morphPhase * morphPhase * morphPhase
      : 1 - (Math.pow(-2 * morphPhase + 2, 3) / 2);

    const x = THREE.MathUtils.lerp(waveX, knotX, easeMorph);
    const y = THREE.MathUtils.lerp(waveY, knotY, easeMorph);
    const z = THREE.MathUtils.lerp(waveZ, knotZ, easeMorph);
    const breathe = 1 + Math.sin(time * 2 + angle * 5) * 0.05;
    points.push(new THREE.Vector3(x * breathe, y * breathe, z * breathe));
  }
  return points;
}

function LoginLoopMark() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mountNode = mountRef.current;
    if (!mountNode) return undefined;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xf6f5f1, 10, 24);

    const { clientWidth, clientHeight } = mountNode;
    const camera = new THREE.PerspectiveCamera(40, clientWidth / clientHeight, 0.1, 100);
    camera.position.set(0, 0, 11.8);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(clientWidth, clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    mountNode.appendChild(renderer.domElement);

    const envMap = createEnvironmentTexture();
    scene.environment = envMap;

    scene.add(new THREE.AmbientLight(0xffffff, 0.52));

    const lightA = new THREE.DirectionalLight(0xffffff, 2.8);
    lightA.position.set(5, 5, 6);
    scene.add(lightA);

    const lightB = new THREE.DirectionalLight(0xffffff, 1.9);
    lightB.position.set(-5, 0, 5);
    scene.add(lightB);

    const material = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color('#2f3338'),
      metalness: 1,
      roughness: 0.08,
      envMap,
      envMapIntensity: 1.95,
      clearcoat: 1,
      clearcoatRoughness: 0,
    });

    const palette = [
      new THREE.Color('#232428'),
      new THREE.Color('#344148'),
      new THREE.Color('#4a433d'),
      new THREE.Color('#3f4943'),
      new THREE.Color('#4a3f46'),
    ];

    const pointCount = 180;
    const tubularSegments = 240;
    const radialSegments = 32;
    const baseRadius = 0.31;

    const initialCurve = new THREE.CatmullRomCurve3(
      getPathPoints(0, 0, pointCount),
      true,
      'centripetal'
    );
    const tubeMesh = new THREE.Mesh(
      new THREE.TubeGeometry(initialCurve, tubularSegments, baseRadius, radialSegments, true),
      material
    );
    scene.add(tubeMesh);

    const clock = new THREE.Clock();
    let frameId = 0;

    const animate = () => {
      frameId = window.requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const cycleDuration = 10;
      const cycleTime = elapsed % cycleDuration;
      const morphPhase = (Math.sin((cycleTime / cycleDuration) * Math.PI * 2 - (Math.PI / 2)) + 1) / 2;
      const palettePhase = ((elapsed * 0.055) % 1) * palette.length;
      const from = palette[Math.floor(palettePhase) % palette.length];
      const to = palette[(Math.floor(palettePhase) + 1) % palette.length];
      material.color.copy(from).lerp(to, palettePhase % 1);

      const newCurve = new THREE.CatmullRomCurve3(
        getPathPoints(elapsed * 0.5, morphPhase, pointCount),
        true,
        'centripetal'
      );
      tubeMesh.geometry.dispose();
      tubeMesh.geometry = new THREE.TubeGeometry(newCurve, tubularSegments, baseRadius, radialSegments, true);
      tubeMesh.rotation.y = elapsed * 0.12;
      tubeMesh.rotation.x = Math.sin(elapsed * 0.07) * 0.18;

      renderer.render(scene, camera);
    };

    const handleResize = () => {
      const width = mountNode.clientWidth;
      const height = mountNode.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    animate();
    window.addEventListener('resize', handleResize);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener('resize', handleResize);
      tubeMesh.geometry.dispose();
      material.dispose();
      envMap.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mountNode) {
        mountNode.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div className="login-loop-card">
      <div className="login-loop-stage" ref={mountRef} />
      <div className="login-loop-crosshair" aria-hidden="true" />
    </div>
  );
}

export default LoginLoopMark;
